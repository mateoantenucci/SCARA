"""Propiedades de cajas equivalentes provisionales, independientes de Webots."""


def box_with_payload(body, payload=0.0):
    if payload < 0:
        raise ValueError("La carga no puede ser negativa")
    mass = body["mass"]
    total = mass + payload
    center = [mass * c / total for c in body["center"]]
    x, y, z = body["size"]
    base_inertia = [mass * (y*y + z*z) / 12,
                    mass * (x*x + z*z) / 12,
                    mass * (x*x + y*y) / 12]
    # Carga cubica de 40 mm centrada en el punto de herramienta.
    inertia = [[0.0] * 3 for _ in range(3)]
    for component_mass, offset in ((mass, [a-b for a,b in zip(body["center"], center)]),
                                   (payload, [-c for c in center])):
        norm2 = sum(v*v for v in offset)
        for i in range(3):
            for j in range(3):
                inertia[i][j] += component_mass * ((norm2 if i == j else 0) - offset[i] * offset[j])
    for i in range(3):
        inertia[i][i] += base_inertia[i] + payload * 0.04**2 / 6
    return total, center, [inertia[0][0], inertia[1][1], inertia[2][2],
                           inertia[0][1], inertia[0][2], inertia[1][2]]
