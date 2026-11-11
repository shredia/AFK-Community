import json
from datetime import datetime

from .utils import num_s


HEADERS = {
    'runs': ['run_id', 'playedAt', 'owner', 'character', 'total_ms', 'total_s', 'bossesKilled', 'rounds', 'source_kind'],
    'equipos': ['run_id', 'playedAt', 'boss_id', 'round_index', 'tiempo_ms', 'tiempo_s', 'bossesKilled', 'golden', 'mascota_id', 'mascota', 'mascota_nivel', 'mascota_jobs', 'heroes_count'],
    'heroes': ['run_id', 'playedAt', 'boss_id', 'round_index', 'tiempo_s', 'slot', 'hero_id', 'hero_tid', 'heroe', 'faccion', 'calidad', 'SI', 'engraving', 'furniture', 'hyper', 'collection_id', 'collection_tid', 'coleccion', 'collection_tag', 'collection_level', 'collection_mythic', 'collection_affixes', 'mascota'],
    'afijos': ['run_id', 'boss_id', 'slot', 'heroe', 'collection_id', 'coleccion', 'afijo_orden', 'nature', 'quality'],
    'errores': ['run_id', 'error'],
}


def procesar_y_ordenar_runs(runs):
    runs_procesadas = []

    for run in runs:
        if not run.get("mine", False):
            continue

        fecha_bruta = run.get("playedAt", "")
        try:
            fecha_obj = datetime.fromisoformat(fecha_bruta.replace("Z", "+00:00"))
            fecha_formateada = fecha_obj.strftime("%Y-%m-%d %H:%M:%S")
        except (TypeError, ValueError):
            fecha_formateada = fecha_bruta

        # Algunas runs (las de temporadas nuevas) traen "result": null
        resultado = run.get("result") or {}
        time_ms = resultado.get("timeMs") or 0
        total_segundos = int(time_ms) // 1000
        minutos = total_segundos // 60
        segundos = total_segundos % 60
        tiempo_legible = f"{minutos} min {segundos} seg"

        runs_procesadas.append({
            "id": run.get("id"),
            "character": run.get("character"),
            "playedAt_raw": fecha_bruta,
            "fecha": fecha_formateada,
            "bossesKilled": resultado.get("bossesKilled", 0),
            "tiempo": tiempo_legible,
            "owner": run.get("owner"),
            "mine": run.get("mine")
        })

    return sorted(runs_procesadas, key=lambda run: run["playedAt_raw"])


def unpack_sources(obj):
    if not isinstance(obj, dict):
        raise ValueError('Respuesta sources no es un objeto JSON')
    if isinstance(obj.get('own'), list):
        return obj['own']
    if isinstance(obj.get('sources'), dict):
        return unpack_sources(obj['sources'])
    raise ValueError('No se encontró lista own en /api/nc-sim/sources')

def flatten(runs):
    out = {k: [] for k in HEADERS}
    for item in runs:
        detail = item.get('detalle') or item.get('detail') or (item if 'rounds' in item else {})
        if not isinstance(detail, dict): continue
        rid = str(item.get('id') or detail.get('id') or '')
        if not rid: continue
        rounds = detail.get('rounds') or []
        played = item.get('playedAt', '')
        result = item.get('result') or {}
        total = result.get('timeMs')
        if total is None and rounds: 
            total = sum((r.get('recorded') or {}).get('timeMs') or 0 for r in rounds)
            
        out['runs'].append(dict(
            run_id=rid, playedAt=played, owner=item.get('owner', ''), 
            character=item.get('character', ''), total_ms=total, total_s=num_s(total), 
            bossesKilled=result.get('bossesKilled', len(rounds)), rounds=len(rounds), 
            source_kind=detail.get('kind', '')
        ))
        
        for r in rounds:
            boss = str(r.get('bossId') or '')
            index = r.get('index', 0)
            rec = r.get('recorded') or {}
            ms = rec.get('timeMs')
            pet = r.get('pet') or {}
            heroes = r.get('heroes') or []
            
            out['equipos'].append(dict(
                run_id=rid, playedAt=played, boss_id=boss, round_index=index, 
                tiempo_ms=ms, tiempo_s=num_s(ms), bossesKilled=rec.get('bossesKilled', ''), 
                golden=r.get('golden'), mascota_id=pet.get('id', ''), mascota=pet.get('name', ''), 
                mascota_nivel=pet.get('level', ''), mascota_jobs='/'.join(map(str, pet.get('jobs') or [])), 
                heroes_count=len(heroes)
            ))
            
            for h in heroes:
                c = h.get('collection') or {}
                slot = h.get('slot', '')
                affixes = c.get('affixes') or []
                
                out['heroes'].append(dict(
                    run_id=rid, playedAt=played, boss_id=boss, round_index=index, 
                    tiempo_s=num_s(ms), slot=slot, hero_id=h.get('id', ''), 
                    hero_tid=h.get('tid', ''), heroe=h.get('name', ''), 
                    faccion=h.get('faction', ''), calidad=h.get('quality', ''), 
                    SI=h.get('sig', ''), engraving=h.get('engraving', ''), 
                    furniture=json.dumps(h.get('furniture'), ensure_ascii=False), 
                    hyper=json.dumps(h.get('hyper'), ensure_ascii=False), 
                    collection_id=c.get('id', ''), collection_tid=c.get('tid', ''), 
                    coleccion=c.get('name', ''), collection_tag=c.get('tag', ''), 
                    collection_level=c.get('level', ''), collection_mythic=c.get('mythic', ''), 
                    collection_affixes=len(affixes), mascota=pet.get('name', '')
                ))
                
                for ai, a in enumerate(affixes, 1):
                    out['afijos'].append(dict(
                        run_id=rid, boss_id=boss, slot=slot, heroe=h.get('name', ''), 
                        collection_id=c.get('id', ''), coleccion=c.get('name', ''), 
                        afijo_orden=ai, nature=a.get('nature', ''), quality=a.get('quality', '')
                    ))
    return out