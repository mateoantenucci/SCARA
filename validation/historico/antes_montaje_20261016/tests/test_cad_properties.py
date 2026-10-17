import itertools
import math
import unittest

from tools.calcular_propiedades_cad import combine, placed, solid_properties

try:
    import OCP
except ImportError:
    OCP = None


def box_properties(origin, size):
    volume = math.prod(size)
    return dict(volume_m3=volume,
                centroid_m=[o+s/2 for o, s in zip(origin, size)],
                inertia_per_density_m5=[
                    [volume*sum(size[k]**2 for k in range(3) if k != i)/12
                     if i == j else 0.0 for j in range(3)] for i in range(3)])


def oblique_transform(translation):
    # Rodrigues: eje (1, 2, -3), distinto de los ejes de ambas cajas.
    axis = [v/math.sqrt(14) for v in (1, 2, -3)]
    cosine, sine = math.cos(.71), math.sin(.71)
    cross = [[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]],
             [-axis[1], axis[0], 0]]
    return [[cosine*(i == j)+(1-cosine)*axis[i]*axis[j]+sine*cross[i][j]
             for j in range(3)]+[translation[i]] for i in range(3)] + [[0, 0, 0, 1]]


class PropertyAssertions:
    def assert_properties_close(self, actual, expected):
        self.assertTrue(math.isclose(actual['volume_m3'], expected['volume_m3'], rel_tol=1e-10))
        for a, e in zip(actual['centroid_m'], expected['centroid_m']):
            self.assertAlmostEqual(a, e, delta=1e-11)
        scale = max(abs(v) for row in expected['inertia_per_density_m5'] for v in row)
        for row_a, row_e in zip(actual['inertia_per_density_m5'], expected['inertia_per_density_m5']):
            for a, e in zip(row_a, row_e):
                self.assertAlmostEqual(a, e, delta=scale*1e-9)


class CADPropertyMathTests(PropertyAssertions, unittest.TestCase):
    def test_rotation_and_aggregation_match_direct_volume_quadrature(self):
        boxes = [([.012, -.023, .031], [.04, .06, .09], oblique_transform([.1, -.2, .3])),
                 ([-.03, .01, -.04], [.07, .02, .05], oblique_transform([-.3, .4, -.1]))]
        result = combine([placed(box_properties(origin, size), transform)
                          for origin, size, transform in boxes])
        # Dos nodos Gauss por coordenada integran exactamente hasta grado tres.
        # Integramos puntos, sin rotar tensores ni aplicar ejes paralelos.
        samples = []
        for origin, size, transform in boxes:
            for signs in itertools.product((-1, 1), repeat=3):
                local = [o+s/2+sign*s/(2*math.sqrt(3))
                         for o, s, sign in zip(origin, size, signs)]
                point = [sum(transform[i][j]*local[j] for j in range(3))+transform[i][3]
                         for i in range(3)]
                samples.append((math.prod(size)/8, point))
        volume = sum(weight for weight, _ in samples)
        center = [sum(weight*point[i] for weight, point in samples)/volume for i in range(3)]
        tensor = [[0.0]*3 for _ in range(3)]
        for weight, point in samples:
            d = [p-c for p, c in zip(point, center)]
            for i in range(3):
                for j in range(3):
                    tensor[i][j] += weight*(sum(d[k]**2 for k in range(3) if k != i)
                                           if i == j else -d[i]*d[j])
        self.assertGreater(abs(tensor[0][1]), 1e-8)
        self.assert_properties_close(result, dict(volume_m3=volume, centroid_m=center,
                                                  inertia_per_density_m5=tensor))

    def test_empty_sum_and_scaled_placement_are_rejected(self):
        with self.assertRaises(ValueError):
            combine([])
        transform = oblique_transform([0, 0, 0])
        transform[0][0] *= 2
        with self.assertRaises(ValueError):
            placed(box_properties([0, 0, 0], [.02, .03, .04]), transform)


@unittest.skipIf(OCP is None, 'El cálculo BREP requiere el Python CAD con OCP')
class CADPropertyKernelTests(PropertyAssertions, unittest.TestCase):
    def test_displaced_box_uses_si_units_and_central_tensor(self):
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt

        shape = BRepPrimAPI_MakeBox(gp_Pnt(10, -20, 30), 40, 60, 80).Shape()
        self.assert_properties_close(solid_properties(shape),
                                     box_properties([.01, -.02, .03], [.04, .06, .08]))

    def test_placed_sum_matches_independent_occt_compound_integration(self):
        from OCP.BRep import BRep_Builder
        from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
        from OCP.BRepGProp import BRepGProp
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.GProp import GProp_GProps
        from OCP.TopoDS import TopoDS_Compound
        from OCP.gp import gp_Pnt, gp_Trsf

        compound, builder = TopoDS_Compound(), BRep_Builder()
        builder.MakeCompound(compound)
        parts = []
        for origin, size, translation in [((10, -20, 30), (40, 60, 80), (.1, -.2, .3)),
                                           ((-30, 10, -40), (70, 20, 50), (-.3, .4, -.1))]:
            shape = BRepPrimAPI_MakeBox(gp_Pnt(*origin), *size).Shape()
            transform = oblique_transform(translation)
            parts.append(placed(solid_properties(shape), transform))
            trsf = gp_Trsf()
            trsf.SetValues(*(transform[i][j]*(1000 if j == 3 else 1)
                             for i in range(3) for j in range(4)))
            builder.Add(compound, BRepBuilderAPI_Transform(shape, trsf, True).Shape())
        # Camino independiente: transformar sólidos BREP e integrar el compound.
        reference = GProp_GProps()
        BRepGProp.VolumeProperties_s(compound, reference, True, True, False)
        center, matrix = reference.CentreOfMass(), reference.MatrixOfInertia()
        expected = dict(volume_m3=reference.Mass()*1e-9,
                        centroid_m=[center.X()*1e-3, center.Y()*1e-3, center.Z()*1e-3],
                        inertia_per_density_m5=[[matrix.Value(i+1, j+1)*1e-15
                                                for j in range(3)] for i in range(3)])
        self.assertGreater(abs(expected['inertia_per_density_m5'][0][1]), 1e-8)
        self.assert_properties_close(combine(parts), expected)

    def test_face_without_closed_shell_is_rejected(self):
        from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
        from OCP.gp import gp_Pln

        with self.assertRaisesRegex(ValueError, 'sin shell cerrado'):
            solid_properties(BRepBuilderAPI_MakeFace(gp_Pln(), 0, 20, 0, 30).Shape())


if __name__ == '__main__':
    unittest.main()
