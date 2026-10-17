"""SCARA-XT-Intersection-1: refine intersection curves before writing STEP.

Adapter for BlinkingSun/sldprt2step fa954124f4f126e0c465c8f96454978ac80b812e
(Apache-2.0; see NOTICE-sldprt2step.txt). The original source stays untouched.
The original 1e-7 m refinement target exceeds STEP's 1e-5 mm uncertainty.
Use 1e-9 m for intersection curves only; retain surfaces, topology, chart
points, fallback behavior and the upstream refinement limits. This target is
not a certified approximation bound. No BREP repair or hole filling occurs.
"""


def install():
    from sldprt2step_lib.step import mapper

    def intersection_curve(self, curve):
        points = self.intersection_points(curve)
        surfaces = self.intersection_evaluators(curve)
        if surfaces is None:
            return points, None
        tangents = mapper._tangents_from_surfaces(points, surfaces)
        if tangents is None:
            return points, None
        return mapper._refine_on_surfaces(points, tangents, surfaces, tol=1e-9)

    mapper.XtStepMapper.intersection_curve = intersection_curve
