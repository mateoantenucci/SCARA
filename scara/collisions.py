"""Separación conservadora del entorno y de herramienta/carga frente a la base.

No usa OCP ni encoders. Las cajas locales vienen del manifiesto CAD vigente;
No comprueba otros pares internos ni obstáculos nuevos.
"""

import itertools
import json
import math
from pathlib import Path

from .frames import chain_frames, transform_point
from .kinematics import validate_joints

ROOT = Path(__file__).resolve().parents[1]
MAX_INTERVALS = 4096


def piece_boxes(cad):
    """Una caja por instancia; conserva la orientación de la caja de pieza."""
    boxes = []
    for part in cad["instances"]:
        bounds = part["bbox_local_m"]
        center = [(bounds[i]+bounds[i+3])/2 for i in range(3)]
        corners = itertools.product(*[(bounds[i], bounds[i+3]) for i in range(3)])
        boxes.append(dict(name=part["instance_name"], group=part["group"],
            source=part["source"], disposition=part["disposition"],
            pose=part["body_from_piece"], center=center,
            size=[bounds[i+3]-bounds[i] for i in range(3)],
            vertices=[transform_point(part["body_from_piece"], p) for p in corners]))
    return boxes


class CollisionChecker:
    def __init__(self, config):
        self.config = config
        cad = json.loads((ROOT/"cad/ensambles/integracion_articulada.json").read_text())
        if any(abs(v-config["geometry"][k]) > 1e-10 for k,v in cad["geometry"].items()):
            raise ValueError("Geometría de colisiones desactualizada; regenerar integración")
        all_boxes = piece_boxes(cad)
        self.boxes = [p for p in all_boxes if p["group"] != "base"]
        policy = config["collision_check"]
        self.margin = policy["margin_m"]
        self.resolution = policy["interval_bound_m"]
        if not (math.isfinite(self.margin) and self.margin >= 0
                and math.isfinite(self.resolution) and self.resolution > 0):
            raise ValueError("Margen/resolución de colisiones inválidos")
        self.obstacles = []
        for obstacle in config["environment"]:
            if (len(obstacle["center"]) != 3 or len(obstacle["size"]) != 3
                    or not all(math.isfinite(v) for v in obstacle["center"]+obstacle["size"])
                    or min(obstacle["size"]) <= 0):
                raise ValueError("Caja de entorno inválida")
            self.obstacles.append(dict(name=obstacle["name"],
                lower=[c-s/2-self.margin for c,s in zip(obstacle["center"],obstacle["size"])],
                upper=[c+s/2+self.margin for c,s in zip(obstacle["center"],obstacle["size"])]))
        # Base es el marco fijo. Solo se compara con herramienta/carga:
        # las cajas de las otras uniones rellenan agujeros de montaje.
        self.fixed_base = [dict(name=p['name'],
            lower=[min(v[i] for v in p['vertices'])-self.margin for i in range(3)],
            upper=[max(v[i] for v in p['vertices'])+self.margin for i in range(3)])
            for p in all_boxes if p['group'] == 'base']

    def first_conflict(self, start, target, payload=0.0):
        """Acota TODO q(s)=start+s(target-start), s∈[0,1], perfil común monótono.

        Cada intervalo usa la AABB en su punto medio ampliada por una cota de
        desplazamiento XY de todos sus vértices. Z es lineal y se acota exacto.
        Si no prueba separación, subdivide; al llegar a resolución, rechaza.
        """
        start, target = validate_joints(start, self.config), validate_joints(target, self.config)
        delta = [b-a for a,b in zip(start,target)]
        boxes = list(self.boxes)
        if payload > 0:
            # Mismo cubo de ensayo de 40 mm de scara/dynamics.py.
            boxes.append(dict(name="carga_cubica_de_ensayo", group="tool",
                              vertices=list(itertools.product((-.02,.02), repeat=3))))
        # Mantener prioridad de los obstáculos externos en el diagnóstico.
        conflict = self._check_boxes(start, delta, boxes, self.obstacles)
        if conflict:
            return conflict
        tool = [p for p in boxes if p['group'] == 'tool']
        return self._check_boxes(start, delta, tool, self.fixed_base)

    def _check_boxes(self, start, delta, boxes, obstacles):
        l1, l2 = (self.config["geometry"][k] for k in ("l1", "l2"))
        processed = 0
        for box in boxes:
            group = box["group"]
            radius = max(math.hypot(p[0],p[1]) for p in box["vertices"])
            if group == "arm":
                speed_bound = radius*abs(delta[0])
            elif group == "forearm":
                speed_bound = l1*abs(delta[0])+radius*abs(delta[0]+delta[1])
            else:
                speed_bound = (l1*abs(delta[0])+l2*abs(delta[0]+delta[1])
                               +radius*abs(sum(delta[:3])))
            intervals = [(0.0,1.0)]
            while intervals:
                lo, hi = intervals.pop()
                mid, half = (lo+hi)/2, (hi-lo)/2
                q = [a+mid*d for a,d in zip(start,delta)]
                processed += 1
                if processed > MAX_INTERVALS:
                    return dict(instance=box['name'],group=group,obstacle='entorno configurado',
                        path_interval=[lo,hi],midpoint_joints=q,
                        displacement_bound_m=max(speed_bound,abs(delta[3]) if group == 'tool' else 0)*half,
                        reason='Presupuesto de intervalos agotado; recorrido no aprobado')
                frame = chain_frames(q,self.config)[group]
                vertices = [transform_point(frame,p) for p in box["vertices"]]
                padding = [speed_bound*half]*2 + [abs(delta[3])*half if group == "tool" else 0.0]
                lower = [min(p[i] for p in vertices)-padding[i] for i in range(3)]
                upper = [max(p[i] for p in vertices)+padding[i] for i in range(3)]
                overlapping = [o for o in obstacles if all(
                    lower[i] <= o["upper"][i] and upper[i] >= o["lower"][i] for i in range(3))]
                if not overlapping:
                    continue
                if max(padding) <= self.resolution or mid in (lo,hi):
                    return dict(instance=box["name"], group=group, obstacle=overlapping[0]["name"],
                        path_interval=[lo,hi], midpoint_joints=q, displacement_bound_m=max(padding),
                        reason=("Precisión numérica agotada; recorrido no aprobado" if mid in (lo,hi)
                                else "No se demuestra separación entre las envolventes con el margen configurado"))
                # ponytail: cotas conservadoras de cajas; OBB/CAD si falsos rechazos limitan el uso.
                intervals.extend(((mid,hi),(lo,mid)))
        return None

    def validate_path(self, start, target, payload=0.0):
        conflict = self.first_conflict(start,target,payload)
        if conflict:
            raise ValueError(f"Recorrido rechazado: {conflict['instance']} puede tocar "
                             f"{conflict['obstacle']} (envolventes y margen {self.margin*1000:g} mm)")
