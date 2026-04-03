import argparse
from pathlib import Path
import re

import pandas as pd


SOURCE_SHEET = "alias_y_desambiguacion_v2"
PRODUCT_SHEET = "productos_priorizados"
FAMILY_SHEET = "familias_sugeridas"
PRESENTATION_SHEET = "presentaciones_canonicas"
RULE_SHEET = "reglas_agente_v2"
OUTPUT_ALIAS_SHEET = "alias_y_desambiguacion_v3"
OUTPUT_FAMILY_SHEET = "familias_sugeridas_v3"
SEED_SHEET = "semillas_curadas_manual"
IMPACT_SHEET = "impacto_semillas"


MANUAL_SEEDS = [
    {
        "seed_id": "abrasivos_lija_agua_abracol",
        "regex": r"LIJA\s+\d+\s+AGUA\s+ABRACOL",
        "marca_match": None,
        "familia_consulta": "lija_agua_abracol",
        "producto_padre_busqueda": "lija de agua abracol",
        "alias_producto": ["lija de agua abracol", "lija de agua", "lija negra", "lija para agua"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "madera, tela, seca, esmeril",
        "pregunta_desambiguacion": "Tengo Lija de Agua Abracol. ¿Qué número de grano buscas (ej. 100, 150, 1000)?",
        "activo_agente": "SI",
        "observaciones_equipo": "Semilla manual curada desde bloque experto de abrasivos.",
    },
    {
        "seed_id": "abrasivos_lija_omega",
        "regex": r"LIJA\s+OMEGA",
        "marca_match": None,
        "familia_consulta": "lija_omega",
        "producto_padre_busqueda": "lija de tela omega",
        "alias_producto": ["lija de tela omega", "lija de tela", "lija para metal", "lija esmeril"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "agua, roja, madera, papel",
        "pregunta_desambiguacion": "Tengo Lija Omega de tela para metal. ¿La necesitas en grano 100, 120 u otro?",
        "activo_agente": "SI",
        "observaciones_equipo": "Semilla manual curada desde bloque experto de abrasivos.",
    },
    {
        "seed_id": "abrasivos_lija_roja_abracol",
        "regex": r"LIJA\s+ROJA\s+ABRACOL",
        "marca_match": None,
        "familia_consulta": "lija_roja_abracol",
        "producto_padre_busqueda": "lija roja abracol",
        "alias_producto": ["lija roja abracol", "lija roja", "lija para madera", "lija abracol roja"],
        "alias_presentacion": [],
        "alias_color": ["roja"],
        "terminos_excluir": "agua, negra, tela, disco",
        "pregunta_desambiguacion": "Tengo Lija Roja Abracol. ¿Qué número buscas (80, 100, 150, 220, 320 u otro)?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de lija roja Abracol detectada en workbook.",
    },
    {
        "seed_id": "abrasivos_disco_corte_abracol",
        "regex": r"DISCO.*ABRACOL\s+CLAVE\s+42[034]",
        "marca_match": None,
        "familia_consulta": "disco_corte_abracol_clave",
        "producto_padre_busqueda": "disco abracol clave",
        "alias_producto": ["disco abracol", "disco de corte abracol", "disco clave abracol", "disco para pulidora abracol"],
        "alias_presentacion": ["4 1/2", "7", "9"],
        "alias_color": [],
        "terminos_excluir": "lija, flap, agua, roja",
        "pregunta_desambiguacion": "Tengo discos Abracol Clave. ¿Lo necesitas de 4 1/2, 7 o 9 pulgadas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de discos Abracol detectada en workbook.",
    },
    {
        "seed_id": "cintas_smith_enmascarar",
        "regex": r"CINTA\s+SMITH",
        "marca_match": None,
        "familia_consulta": "cinta_smith_enmascarar",
        "producto_padre_busqueda": "cinta de enmascarar smith",
        "alias_producto": ["cinta de enmascarar", "cinta de papel", "tirro", "cinta smith"],
        "alias_presentacion": ["1/2", "3/4", "1 pulgada"],
        "alias_color": [],
        "terminos_excluir": "empaque, transparente, aislante",
        "pregunta_desambiguacion": "Tengo cinta de enmascarar Smith. ¿La buscas de 1/2, 3/4 o 1 pulgada?",
        "activo_agente": "SI",
        "observaciones_equipo": "Semilla manual curada desde bloque experto de cintas.",
    },
    {
        "seed_id": "cintas_abracol_enmascarar",
        "regex": r"CINTA\s+DE\s+ENMASCARAR\s+ABRACOL",
        "marca_match": None,
        "familia_consulta": "cinta_abracol_enmascarar",
        "producto_padre_busqueda": "cinta de enmascarar abracol",
        "alias_producto": ["cinta abracol", "cinta de enmascarar abracol", "tirro abracol", "cinta de papel abracol"],
        "alias_presentacion": ["3/4", "1 1/2"],
        "alias_color": [],
        "terminos_excluir": "doble faz, transparente, cubrefacil, smith",
        "pregunta_desambiguacion": "Tengo cinta de enmascarar Abracol. ¿La buscas de 3/4 o de 1 1/2?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de cintas Abracol detectada en workbook.",
    },
    {
        "seed_id": "goya_brocha_popular",
        "regex": r"BROCHA\s+GOYA\s+POPULAR",
        "marca_match": None,
        "familia_consulta": "brocha_goya_popular",
        "producto_padre_busqueda": "brocha economica goya",
        "alias_producto": ["brocha economica", "brocha de cerda", "brocha normal", "brocha goya"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "profesional, plastico, nylon",
        "pregunta_desambiguacion": "Tengo la Brocha Goya Popular. ¿De qué medida la necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Semilla manual curada desde bloque experto de aplicación.",
    },
    {
        "seed_id": "goya_brocha_profesional",
        "regex": r"BROCHA\s+GOYA\s+PROF",
        "marca_match": None,
        "familia_consulta": "brocha_goya_profesional",
        "producto_padre_busqueda": "brocha profesional goya",
        "alias_producto": ["brocha profesional goya", "brocha goya profesional", "brocha fina goya", "brocha goya"],
        "alias_presentacion": ["1/2", "1", "1 1/2", "2", "2 1/2", "3", "4", "5"],
        "alias_color": [],
        "terminos_excluir": "popular, economica, plastico, nylon",
        "pregunta_desambiguacion": "Tengo Brocha Goya Profesional. ¿De qué medida la necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de brocha profesional Goya detectada en workbook.",
    },
    {
        "seed_id": "goya_rodillo_junior_felpa",
        "regex": r"RODILLO\s+JUNIOR\s+FELPA\s+GOYA",
        "marca_match": None,
        "familia_consulta": "rodillo_junior_felpa_goya",
        "producto_padre_busqueda": "rodillo felpa goya pequeño",
        "alias_producto": ["rodillito", "rodillo pequeño", "rodillo para retoques", "rodillo felpa goya"],
        "alias_presentacion": ["2 pulgadas", "4 pulgadas"],
        "alias_color": [],
        "terminos_excluir": "epoxico, hilo, espuma, gigante",
        "pregunta_desambiguacion": "Tengo el Rodillo Junior de Felpa Goya. ¿Lo llevas de 2 o de 4 pulgadas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Semilla manual curada desde bloque experto de aplicación.",
    },
    {
        "seed_id": "goya_rodillo_hilo_profesional",
        "regex": r"RODILLO\s+HILO\s+PROFESIONAL\s+GOYA",
        "marca_match": None,
        "familia_consulta": "rodillo_hilo_profesional_goya",
        "producto_padre_busqueda": "rodillo hilo profesional goya",
        "alias_producto": ["rodillo hilo goya", "rodillo profesional goya", "rodillo de hilo", "rodillo goya"],
        "alias_presentacion": ["9"],
        "alias_color": [],
        "terminos_excluir": "junior, felpa, espuma, epoxico",
        "pregunta_desambiguacion": "Tengo Rodillo Hilo Profesional Goya. ¿Lo necesitas de 9 pulgadas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de rodillo hilo profesional Goya detectada en workbook.",
    },
    {
        "seed_id": "goya_rodillo_espuma_blanca",
        "regex": r"RODILLO\s+ESPUMA\s+BLANCA\s+GOYA",
        "marca_match": None,
        "familia_consulta": "rodillo_espuma_blanca_goya",
        "producto_padre_busqueda": "rodillo espuma blanca goya",
        "alias_producto": ["rodillo espuma goya", "rodillo espuma blanca", "rodillo de espuma", "rodillo goya espuma"],
        "alias_presentacion": ["3", "4", "6"],
        "alias_color": ["blanca"],
        "terminos_excluir": "felpa, hilo, epoxico, junior",
        "pregunta_desambiguacion": "Tengo Rodillo Espuma Blanca Goya. ¿Lo buscas de 3, 4 o 6 pulgadas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de rodillo espuma blanca Goya detectada en workbook.",
    },
    {
        "seed_id": "goya_rodillo_epoxico",
        "regex": r"RODILLO\s+EPOXICO.*GOYA",
        "marca_match": None,
        "familia_consulta": "rodillo_epoxico_goya",
        "producto_padre_busqueda": "rodillo epoxico goya",
        "alias_producto": ["rodillo epoxico goya", "rodillo para epoxico", "rodillo epoxico", "rodillo goya blanco"],
        "alias_presentacion": ["9"],
        "alias_color": ["blanco"],
        "terminos_excluir": "felpa, hilo, espuma, junior",
        "pregunta_desambiguacion": "Tengo Rodillo Epóxico Goya. ¿Lo necesitas de 9 pulgadas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de rodillo epóxico Goya detectada en workbook.",
    },
    {
        "seed_id": "viniltex_blanco",
        "regex": r"VINILTEX.*BLAN(CO|\s+PURO)",
        "marca_match": r"VINILTEX|PINTUCO",
        "familia_consulta": "viniltex_blanco",
        "producto_padre_busqueda": "viniltex blanco",
        "alias_producto": ["viniltex blanco", "viniltex", "pintura viniltex blanca", "viniltex blanco puro"],
        "alias_presentacion": ["cuñete", "caneca", "cubeta", "1/5", "galon", "1/1", "cuarto", "1/4"],
        "alias_color": ["blanco", "blanco puro"],
        "terminos_excluir": "pintulux, koraza, domestico, aerosol",
        "pregunta_desambiguacion": "Tengo Viniltex Blanco. ¿Lo llevas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Viniltex blanco detectada en workbook.",
    },
    {
        "seed_id": "viniltex_base_pastel",
        "regex": r"VINILTEX.*(PASTEL|B\s*PASTE)",
        "marca_match": r"VINILTEX|PINTUCO",
        "familia_consulta": "viniltex_base_pastel",
        "producto_padre_busqueda": "viniltex base pastel",
        "alias_producto": ["viniltex pastel", "base pastel viniltex", "viniltex base pastel", "viniltex para entonar pastel"],
        "alias_presentacion": ["cuñete", "galon", "cuarto"],
        "alias_color": [],
        "terminos_excluir": "deep, accent, blanco, negro",
        "pregunta_desambiguacion": "Tengo Viniltex Base Pastel. ¿La buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de bases Viniltex pastel detectada en workbook.",
    },
    {
        "seed_id": "viniltex_base_deep",
        "regex": r"VINILTEX.*DEEP",
        "marca_match": r"VINILTEX|PINTUCO",
        "familia_consulta": "viniltex_base_deep",
        "producto_padre_busqueda": "viniltex base deep",
        "alias_producto": ["viniltex deep", "base deep viniltex", "viniltex base deep", "viniltex para colores intensos"],
        "alias_presentacion": ["cuñete", "galon", "cuarto"],
        "alias_color": [],
        "terminos_excluir": "pastel, accent, blanco",
        "pregunta_desambiguacion": "Tengo Viniltex Base Deep. ¿La buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de bases Viniltex deep detectada en workbook.",
    },
    {
        "seed_id": "viniltex_base_tint",
        "regex": r"VINILTEX.*TINT",
        "marca_match": r"VINILTEX|PINTUCO",
        "familia_consulta": "viniltex_base_tint",
        "producto_padre_busqueda": "viniltex base tint",
        "alias_producto": ["viniltex tint", "base tint viniltex", "viniltex base tint", "viniltex para entonar"],
        "alias_presentacion": ["cuarto", "galon", "cuñete"],
        "alias_color": [],
        "terminos_excluir": "pastel, deep, blanco",
        "pregunta_desambiguacion": "Tengo Viniltex Base Tint. ¿La buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de bases Viniltex tint detectada en workbook.",
    },
    {
        "seed_id": "domestico_blanco_p11",
        "regex": r"DOMESTICO.*BLANCO.*(P-?11|6W)",
        "marca_match": r"DOMESTICO|PINTUCO",
        "familia_consulta": "domestico_blanco_p11",
        "producto_padre_busqueda": "domestico blanco",
        "alias_producto": ["domestico blanco", "blanca economica", "p11", "pintura economica blanca"],
        "alias_presentacion": ["cuarto", "galon", "cuñete", "1/4", "1/1", "1/5"],
        "alias_color": ["blanco"],
        "terminos_excluir": "pintulux, viniltex, koraza",
        "pregunta_desambiguacion": "Tengo Doméstico Blanco. ¿Lo buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Doméstico blanco P-11 detectada en workbook.",
    },
    {
        "seed_id": "domestico_verde_esmeralda_p53",
        "regex": r"DOMESTICO.*VERDE\s+ESMER.*P-?53",
        "marca_match": r"DOMESTICO|PINTUCO",
        "familia_consulta": "domestico_verde_esmeralda_p53",
        "producto_padre_busqueda": "domestico verde esmeralda",
        "alias_producto": ["domestico verde esmeralda", "p53", "verde esmeralda domestico", "verde esmeralda p11"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["verde esmeralda"],
        "terminos_excluir": "verde selva, pintulux, viniltex",
        "pregunta_desambiguacion": "Tengo Doméstico Verde Esmeralda P-53. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Doméstico verde esmeralda P-53 detectada en workbook.",
    },
    {
        "seed_id": "domestico_rojo_fiesta_p30",
        "regex": r"DOMESTICO.*ROJO\s+FIESTA.*P-?30",
        "marca_match": r"DOMESTICO|PINTUCO",
        "familia_consulta": "domestico_rojo_fiesta_p30",
        "producto_padre_busqueda": "domestico rojo fiesta",
        "alias_producto": ["domestico rojo fiesta", "p30", "rojo fiesta domestico", "rojo fiesta"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["rojo fiesta"],
        "terminos_excluir": "rojo vivo, pintulux, viniltex",
        "pregunta_desambiguacion": "Tengo Doméstico Rojo Fiesta P-30. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Doméstico rojo fiesta P-30 detectada en workbook.",
    },
    {
        "seed_id": "pintulux_blanco_brillante",
        "regex": r"PINTULUX.*BR.*BLANCO\s+11",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_blanco_brillante",
        "producto_padre_busqueda": "pintulux blanco brillante",
        "alias_producto": ["pintulux blanco", "t11", "pintulux blanco brillante", "blanco pintulux"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["blanco"],
        "terminos_excluir": "mate, domestico, viniltex",
        "pregunta_desambiguacion": "Tengo Pintulux Blanco Brillante. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux blanco brillante detectada en workbook.",
    },
    {
        "seed_id": "pintulux_blanco_mate",
        "regex": r"PINTULUX.*MAT.*BLANCO\s+10",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_blanco_mate",
        "producto_padre_busqueda": "pintulux blanco mate",
        "alias_producto": ["pintulux blanco mate", "blanco mate pintulux", "pintulux mate blanco", "t11 mate"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["blanco mate"],
        "terminos_excluir": "brillante, domestico, viniltex",
        "pregunta_desambiguacion": "Tengo Pintulux Blanco Mate. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux blanco mate detectada en workbook.",
    },
    {
        "seed_id": "pintulux_negro_brillante",
        "regex": r"PINTULUX.*BR.*NEGRO\s+95",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_negro_brillante",
        "producto_padre_busqueda": "pintulux negro brillante",
        "alias_producto": ["pintulux negro", "negro pintulux", "pintulux negro brillante", "negro 95"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["negro"],
        "terminos_excluir": "mate, domestico, viniltex",
        "pregunta_desambiguacion": "Tengo Pintulux Negro Brillante. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux negro brillante detectada en workbook.",
    },
    {
        "seed_id": "pintulux_negro_mate",
        "regex": r"PINTULUX.*MAT.*NEGRO\s+89",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_negro_mate",
        "producto_padre_busqueda": "pintulux negro mate",
        "alias_producto": ["pintulux negro mate", "negro mate pintulux", "pintulux mate negro", "negro 89"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["negro mate"],
        "terminos_excluir": "brillante, domestico, viniltex",
        "pregunta_desambiguacion": "Tengo Pintulux Negro Mate. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux negro mate detectada en workbook.",
    },
    {
        "seed_id": "pintulux_verde_bronce",
        "regex": r"PINTULUX.*VERDE\s+BRON",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_verde_bronce",
        "producto_padre_busqueda": "pintulux verde bronce",
        "alias_producto": ["pintulux verde bronce", "verde bronce pintulux", "verde bronce", "pintulux verde"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["verde bronce"],
        "terminos_excluir": "bronce 77, aluminio, dorado",
        "pregunta_desambiguacion": "Tengo Pintulux Verde Bronce. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux verde bronce detectada en workbook.",
    },
    {
        "seed_id": "pintulux_bronce_77",
        "regex": r"PINTULUX.*BRONCE\s+77",
        "marca_match": r"PINTULUX|PINTUCO",
        "familia_consulta": "pintulux_bronce_77",
        "producto_padre_busqueda": "pintulux bronce 77",
        "alias_producto": ["pintulux bronce", "bronce pintulux", "bronce 77", "pintulux bronce 77"],
        "alias_presentacion": ["cuarto", "galon"],
        "alias_color": ["bronce"],
        "terminos_excluir": "verde bronce, aluminio, dorado",
        "pregunta_desambiguacion": "Tengo Pintulux Bronce 77. ¿Lo buscas en cuarto o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Pintulux bronce 77 detectada en workbook.",
    },
    {
        "seed_id": "koraza_blanco",
        "regex": r"KORAZA.*BLANCO",
        "marca_match": r"KORAZA|PINTUCO",
        "familia_consulta": "koraza_blanco",
        "producto_padre_busqueda": "koraza blanco",
        "alias_producto": ["koraza blanco", "koraza", "impermeabilizante koraza blanco", "koraza pintura blanca"],
        "alias_presentacion": ["cuarto", "galon", "cuñete"],
        "alias_color": ["blanco"],
        "terminos_excluir": "pastel, deep, tint, viniltex",
        "pregunta_desambiguacion": "Tengo Koraza Blanco. ¿Lo buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Koraza blanco detectada en workbook.",
    },
    {
        "seed_id": "koraza_base_pastel",
        "regex": r"KORAZA.*BASE\s+PASTEL",
        "marca_match": r"KORAZA|PINTUCO",
        "familia_consulta": "koraza_base_pastel",
        "producto_padre_busqueda": "koraza base pastel",
        "alias_producto": ["koraza pastel", "base pastel koraza", "koraza base pastel", "koraza para entonar pastel"],
        "alias_presentacion": ["cuarto", "galon", "cuñete"],
        "alias_color": [],
        "terminos_excluir": "deep, tint, blanco",
        "pregunta_desambiguacion": "Tengo Koraza Base Pastel. ¿La buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Koraza base pastel detectada en workbook.",
    },
    {
        "seed_id": "koraza_base_deep",
        "regex": r"KORAZA.*DEEP\s+BASE",
        "marca_match": r"KORAZA|PINTUCO",
        "familia_consulta": "koraza_base_deep",
        "producto_padre_busqueda": "koraza base deep",
        "alias_producto": ["koraza deep", "base deep koraza", "koraza base deep", "koraza para colores intensos"],
        "alias_presentacion": ["cuarto", "galon", "cuñete"],
        "alias_color": [],
        "terminos_excluir": "pastel, tint, blanco",
        "pregunta_desambiguacion": "Tengo Koraza Base Deep. ¿La buscas en cuarto, galón o cuñete?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Koraza base deep detectada en workbook.",
    },
    {
        "seed_id": "montana_94_blanco_mate",
        "regex": r"MONTANA\s+94.*BLANCO",
        "marca_match": r"MONTANA",
        "familia_consulta": "montana_94_blanco_mate",
        "producto_padre_busqueda": "aerosol montana 94 blanco",
        "alias_producto": ["aerosol montana 94", "spray", "pintura en aerosol", "spray montana"],
        "alias_presentacion": ["tarro", "lata", "spray", "aerosol"],
        "alias_color": ["blanco", "blanco mate"],
        "terminos_excluir": "galon, cuñete, cuarto, caneca, brocha, rodillo",
        "pregunta_desambiguacion": "Tengo Aerosol Montana 94 Mate. ¿Cuántas latas de color Blanco necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Revisar que nunca se asocie a galón.",
    },
    {
        "seed_id": "yale_candados",
        "regex": r"CANDADO.*YALE",
        "marca_match": r"YALE",
        "familia_consulta": "candado_yale",
        "producto_padre_busqueda": "candado yale",
        "alias_producto": ["candado yale", "candado dorado", "candado tradicional", "candado de bronce"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "clave, guaya, antizizalla, segurex",
        "pregunta_desambiguacion": "Tengo candados Yale. ¿De qué tamaño lo buscas (ej. 30mm, 40mm, 50mm)?",
        "activo_agente": "SI",
        "observaciones_equipo": "Aplicar solo a candados Yale, no a cerraduras.",
    },
    {
        "seed_id": "yale_candado_italiano",
        "regex": r"CANDADO\s+ITALIANO\s+YALE",
        "marca_match": r"YALE",
        "familia_consulta": "candado_italiano_yale",
        "producto_padre_busqueda": "candado italiano yale",
        "alias_producto": ["candado italiano yale", "candado yale italiano", "candado yale 110", "candado yale"],
        "alias_presentacion": ["30mm", "40mm", "50mm", "60mm", "70mm"],
        "alias_color": [],
        "terminos_excluir": "aleman, segurex, cerradura, mueble",
        "pregunta_desambiguacion": "Tengo Candado Italiano Yale. ¿De qué tamaño lo buscas: 30, 40, 50, 60 o 70 mm?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de candado italiano Yale detectada en workbook.",
    },
    {
        "seed_id": "yale_candado_aleman",
        "regex": r"CANDADO\s+ALEMAN.*YALE",
        "marca_match": r"YALE",
        "familia_consulta": "candado_aleman_yale",
        "producto_padre_busqueda": "candado aleman yale",
        "alias_producto": ["candado aleman yale", "candado yale aleman", "candado yale 800", "candado yale"],
        "alias_presentacion": ["70mm"],
        "alias_color": [],
        "terminos_excluir": "italiano, segurex, cerradura, mueble",
        "pregunta_desambiguacion": "Tengo Candado Alemán Yale. ¿Lo buscas de 70 mm?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de candado alemán Yale detectada en workbook.",
    },
    {
        "seed_id": "yale_cerradura_sobreponer",
        "regex": r"CERRADURA\s+YALE\s+SOBREPONER",
        "marca_match": r"YALE",
        "familia_consulta": "cerradura_yale_sobreponer",
        "producto_padre_busqueda": "cerradura yale sobreponer",
        "alias_producto": ["cerradura yale sobreponer", "cerradura yale", "chapa yale sobreponer", "sobreponer yale"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "candado, mueble, manija, digital",
        "pregunta_desambiguacion": "Tengo cerradura Yale de sobreponer. ¿La necesitas derecha o izquierda?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de cerradura Yale sobreponer detectada en workbook.",
    },
    {
        "seed_id": "yale_manija_alcoba",
        "regex": r"MANIJA\s+FILADELFIA\s+YALE\s+ALCOBA",
        "marca_match": r"YALE",
        "familia_consulta": "manija_yale_alcoba",
        "producto_padre_busqueda": "manija yale alcoba",
        "alias_producto": ["manija yale alcoba", "cerradura yale alcoba", "manija filadelfia yale", "chapa alcoba yale"],
        "alias_presentacion": [],
        "alias_color": [],
        "terminos_excluir": "bano, baño, principal, candado",
        "pregunta_desambiguacion": "Tengo Manija Yale para alcoba. ¿Cuántas necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de manija Yale alcoba detectada en workbook.",
    },
    {
        "seed_id": "yale_mueble_estandar",
        "regex": r"MUEBLE\s+ESTA[NÑ]DAR.*YALE",
        "marca_match": r"YALE",
        "familia_consulta": "mueble_estandar_yale",
        "producto_padre_busqueda": "mueble estandar yale",
        "alias_producto": ["mueble yale", "mueble estandar yale", "cerradura de mueble yale", "yale b420"],
        "alias_presentacion": [],
        "alias_color": ["cromo", "niquel"],
        "terminos_excluir": "candado, sobreponer, alcoba, digital",
        "pregunta_desambiguacion": "Tengo muebles Yale. ¿Cuál referencia buscas: B420, B430, B450 o B460?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de mueble estándar Yale detectada en workbook.",
    },
    {
        "seed_id": "segurex_cerrojo",
        "regex": r"CERROJO.*SEGUREX",
        "marca_match": r"SEGUREX",
        "familia_consulta": "cerrojo_segurex",
        "producto_padre_busqueda": "cerrojo segurex",
        "alias_producto": ["cerrojo segurex", "cerrojo cromado segurex", "segurex cerrojo", "seguro segurex"],
        "alias_presentacion": [],
        "alias_color": ["cromado mate"],
        "terminos_excluir": "yale, candado, cerradura inteligente",
        "pregunta_desambiguacion": "Tengo cerrojos Segurex. ¿Buscas el B360 o el B362?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de cerrojos Segurex detectada en workbook.",
    },
    {
        "seed_id": "artecola_pl285_madera",
        "regex": r"PL\s*285\s+MADERA|PL285\s+MADERA",
        "marca_match": None,
        "familia_consulta": "pl285_madera",
        "producto_padre_busqueda": "pegante pl285 madera",
        "alias_producto": ["pl285", "pegante pl285", "pegante madera pl285", "pegante para madera"],
        "alias_presentacion": ["30gr", "60ml", "120ml", "375ml", "750ml", "galon"],
        "alias_color": [],
        "terminos_excluir": "afix, contacto, silicona, pvc",
        "pregunta_desambiguacion": "Tengo PL285 para madera. ¿Lo necesitas de 30gr, 60ml, 120ml, 375ml, 750ml o galón?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de PL285 madera detectada en workbook.",
    },
    {
        "seed_id": "afix_silicona_acetica",
        "regex": r"SILICONA\s+AC[ÉE]TICA\s+AFIX",
        "marca_match": r"AFIX",
        "familia_consulta": "silicona_acetica_afix",
        "producto_padre_busqueda": "silicona acetica afix",
        "alias_producto": ["silicona afix", "silicona acetica afix", "silicona blanca afix", "silicona transparente afix"],
        "alias_presentacion": ["50ml"],
        "alias_color": ["blanca", "transparente"],
        "terminos_excluir": "sellador, espuma, epoxi, fija roscas",
        "pregunta_desambiguacion": "Tengo Silicona Acética Afix. ¿La buscas blanca o transparente?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de silicona acética Afix detectada en workbook.",
    },
    {
        "seed_id": "afix_sellador_acrilico",
        "regex": r"AFIX\s+GREEN\s+SELLADOR\s+ACRILICO",
        "marca_match": r"AFIX",
        "familia_consulta": "sellador_acrilico_afix",
        "producto_padre_busqueda": "sellador acrilico afix",
        "alias_producto": ["sellador acrilico afix", "afix green", "sellador afix", "sellador acrilico"],
        "alias_presentacion": ["430gr"],
        "alias_color": [],
        "terminos_excluir": "silicona, espuma, epoxi, pl285",
        "pregunta_desambiguacion": "Tengo Sellador Acrílico Afix Green de 430gr. ¿Cuántos necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de sellador acrílico Afix detectada en workbook.",
    },
    {
        "seed_id": "afix_fija_roscas",
        "regex": r"AFIX\s+FIJA\s+ROSCAS",
        "marca_match": r"AFIX",
        "familia_consulta": "fija_roscas_afix",
        "producto_padre_busqueda": "fija roscas afix",
        "alias_producto": ["fija roscas afix", "traba roscas afix", "pegante roscas", "afix fija roscas"],
        "alias_presentacion": ["10gr"],
        "alias_color": [],
        "terminos_excluir": "silicona, espuma, epoxi, sellador",
        "pregunta_desambiguacion": "Tengo Fija Roscas Afix de 10gr. ¿Cuántos necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de fija roscas Afix detectada en workbook.",
    },
    {
        "seed_id": "afix_espuma_poliuretano",
        "regex": r"ESPUMA\s+DE\s+POLIURETANO\s+AFIX",
        "marca_match": r"AFIX",
        "familia_consulta": "espuma_poliuretano_afix",
        "producto_padre_busqueda": "espuma poliuretano afix",
        "alias_producto": ["espuma afix", "espuma de poliuretano afix", "espuma expansiva afix", "espuma poliuretano"],
        "alias_presentacion": ["500ml"],
        "alias_color": [],
        "terminos_excluir": "silicona, epoxi, sellador, pl285",
        "pregunta_desambiguacion": "Tengo Espuma de Poliuretano Afix de 500ml. ¿Cuántas unidades necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de espuma de poliuretano Afix detectada en workbook.",
    },
    {
        "seed_id": "afix_epoxi_transparente",
        "regex": r"AFIX\s+ADHESIVO\s+EPOXI\s+TRANSP",
        "marca_match": r"AFIX",
        "familia_consulta": "epoxi_transparente_afix",
        "producto_padre_busqueda": "epoxi transparente afix",
        "alias_producto": ["epoxi afix", "adhesivo epoxi afix", "epoxi transparente afix", "pegante epoxi"],
        "alias_presentacion": ["6gr"],
        "alias_color": ["transparente"],
        "terminos_excluir": "silicona, pl285, fija roscas, sellador",
        "pregunta_desambiguacion": "Tengo Adhesivo Epóxico Transparente Afix de 6gr. ¿Cuántos necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de epoxi transparente Afix detectada en workbook.",
    },
    {
        "seed_id": "afix_turbo_max",
        "regex": r"TURBO\s+MAX\s+AFIX",
        "marca_match": r"AFIX",
        "familia_consulta": "turbo_max_afix",
        "producto_padre_busqueda": "turbo max afix",
        "alias_producto": ["turbo max afix", "pegante turbo max", "afix turbo max", "adhesivo afix"],
        "alias_presentacion": ["446gr"],
        "alias_color": [],
        "terminos_excluir": "silicona, epoxi, espuma, pl285",
        "pregunta_desambiguacion": "Tengo Turbo Max Afix de 446gr. ¿Cuántos necesitas?",
        "activo_agente": "SI",
        "observaciones_equipo": "Familia real de Turbo Max Afix detectada en workbook.",
    },
]


def clean_text(value):
    if pd.isna(value):
        return None
    text = str(value).strip()
    return text or None


def normalize_key(value):
    value = clean_text(value)
    if not value:
        return None
    value = re.sub(r"^\d+(?:[_\s-]+)", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value or None


def normalize_alias_value(value):
    value = clean_text(value)
    if not value:
        return None
    value = re.sub(r"\s+", " ", value).strip()
    if value in {"0", "0.0"}:
        return None
    return value or None


def set_alias_columns(row, prefix, values, limit):
    normalized_values = []
    seen = set()
    for value in values:
        cleaned = normalize_alias_value(value)
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized_values.append(cleaned)

    for index in range(limit):
        column_name = f"{prefix}_{index + 1}"
        row[column_name] = normalized_values[index] if index < len(normalized_values) else None
    return row


def seed_matches(row, seed):
    description = clean_text(row.get("descripcion_base")) or ""
    if not re.search(seed["regex"], description, flags=re.IGNORECASE):
        return False
    if seed.get("marca_match"):
        marca = clean_text(row.get("marca")) or ""
        if not re.search(seed["marca_match"], marca, flags=re.IGNORECASE) and not re.search(seed["marca_match"], description, flags=re.IGNORECASE):
            return False
    return True


def build_manual_seed_dataframe():
    records = []
    for seed in MANUAL_SEEDS:
        records.append(
            {
                "seed_id": seed["seed_id"],
                "regex": seed["regex"],
                "familia_consulta": seed["familia_consulta"],
                "producto_padre_busqueda": seed["producto_padre_busqueda"],
                "alias_producto": ", ".join(seed["alias_producto"]),
                "alias_presentacion": ", ".join(seed["alias_presentacion"]),
                "alias_color": ", ".join(seed["alias_color"]),
                "terminos_excluir": seed["terminos_excluir"],
                "pregunta_desambiguacion": seed["pregunta_desambiguacion"],
                "activo_agente": seed["activo_agente"],
                "observaciones_equipo": seed["observaciones_equipo"],
            }
        )
    return pd.DataFrame.from_records(records)


def apply_seeds(alias_df):
    updated_df = alias_df.copy()
    impact_rows = []

    editable_columns = [
        "familia_consulta",
        "producto_padre_busqueda",
        "pregunta_desambiguacion",
        "terminos_excluir",
        "activo_agente",
        "observaciones_equipo",
        "alias_producto_1",
        "alias_producto_2",
        "alias_producto_3",
        "alias_producto_4",
        "alias_producto_5",
        "alias_presentacion_1",
        "alias_presentacion_2",
        "alias_presentacion_3",
        "alias_presentacion_4",
        "alias_presentacion_5",
        "alias_color_1",
        "alias_color_2",
        "alias_color_3",
    ]
    for column_name in editable_columns:
        if column_name in updated_df.columns:
            updated_df[column_name] = updated_df[column_name].astype(object)

    for column_name in ["familia_consulta", "producto_padre_busqueda", "alias_producto_1", "alias_producto_2", "alias_producto_3", "alias_producto_4", "alias_producto_5"]:
        if column_name in updated_df.columns:
            updated_df[column_name] = updated_df[column_name].apply(normalize_key)

    total_matches = 0
    for seed in MANUAL_SEEDS:
        mask = updated_df.apply(lambda row: seed_matches(row, seed), axis=1)
        matched = int(mask.sum())
        total_matches += matched
        if matched == 0:
            impact_rows.append({"seed_id": seed["seed_id"], "matched_rows": 0, "familia_consulta": seed["familia_consulta"]})
            continue

        updated_df.loc[mask, "familia_consulta"] = seed["familia_consulta"]
        updated_df.loc[mask, "producto_padre_busqueda"] = seed["producto_padre_busqueda"]
        updated_df.loc[mask, "pregunta_desambiguacion"] = seed["pregunta_desambiguacion"]
        updated_df.loc[mask, "terminos_excluir"] = seed["terminos_excluir"]
        updated_df.loc[mask, "activo_agente"] = seed["activo_agente"]

        for row_index in updated_df[mask].index:
            row = updated_df.loc[row_index].copy()
            row = set_alias_columns(row, "alias_producto", seed["alias_producto"], 5)
            row = set_alias_columns(row, "alias_presentacion", seed["alias_presentacion"], 5)
            row = set_alias_columns(row, "alias_color", seed["alias_color"], 3)
            existing_note = clean_text(row.get("observaciones_equipo"))
            seed_note = seed["observaciones_equipo"]
            if existing_note and seed_note.lower() not in existing_note.lower():
                row["observaciones_equipo"] = f"{existing_note} | {seed_note}"
            elif not existing_note:
                row["observaciones_equipo"] = seed_note
            updated_df.loc[row_index] = row

        impact_rows.append({
            "seed_id": seed["seed_id"],
            "matched_rows": matched,
            "familia_consulta": seed["familia_consulta"],
        })

    return updated_df, pd.DataFrame.from_records(impact_rows), total_matches


def build_family_v3(products_df, alias_v3_df):
    merged = alias_v3_df.merge(
        products_df[["producto_codigo", "stock_total", "ventas_unidades_total", "ventas_valor_total", "marca", "core_descriptor", "color_raiz"]],
        on="producto_codigo",
        how="left",
        suffixes=("", "_producto"),
    )

    merged["marca_final"] = merged["marca"].where(merged["marca"].notna(), merged.get("marca_producto"))
    grouped = (
        merged.groupby(["familia_consulta", "producto_padre_busqueda"], dropna=False)
        .agg(
            marca=("marca_final", lambda values: next((value for value in values if clean_text(value)), None)),
            core_descriptor=("core_descriptor", lambda values: next((value for value in values if clean_text(value)), None)),
            color_raiz=("color_raiz", lambda values: next((value for value in values if clean_text(value)), None)),
            productos=("producto_codigo", "nunique"),
            ventas_unidades_total=("ventas_unidades_total", "sum"),
            ventas_valor_total=("ventas_valor_total", "sum"),
            stock_total=("stock_total", "sum"),
            pregunta_desambiguacion_sugerida=("pregunta_desambiguacion", lambda values: next((value for value in values if clean_text(value)), None)),
            estrategia_busqueda=("estrategia_busqueda", lambda values: next((value for value in values if clean_text(value)), None)),
            variantes_top=("descripcion_base", lambda values: " | ".join(list(dict.fromkeys([value for value in values if clean_text(value)]))[:6])),
        )
        .reset_index()
    )

    grouped = grouped.rename(columns={"familia_consulta": "familia_consulta_sugerida"})
    grouped["requiere_desambiguacion"] = grouped["productos"].fillna(0).astype(int) > 1
    return grouped


def build_output_path(input_path):
    stem = input_path.stem
    if stem.endswith("_v2"):
        stem = stem[:-3]
    return input_path.with_name(f"{stem}_v3_semillas.xlsx")


def main():
    parser = argparse.ArgumentParser(description="Aplica semillas manuales de alta confianza al workbook del catálogo del agente.")
    parser.add_argument(
        "--excel",
        type=str,
        default="artifacts/Plantilla_Agente_Catalogo_Ferreinox_v2.xlsx",
        help="Ruta al workbook V2",
    )
    args = parser.parse_args()

    input_path = Path(args.excel).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"No se encontró el workbook: {input_path}")

    products_df = pd.read_excel(input_path, sheet_name=PRODUCT_SHEET)
    alias_df = pd.read_excel(input_path, sheet_name=SOURCE_SHEET)
    presentations_df = pd.read_excel(input_path, sheet_name=PRESENTATION_SHEET)
    rules_df = pd.read_excel(input_path, sheet_name=RULE_SHEET)

    alias_v3_df, impact_df, total_matches = apply_seeds(alias_df)
    family_v3_df = build_family_v3(products_df, alias_v3_df)
    manual_seed_df = build_manual_seed_dataframe()

    output_path = build_output_path(input_path)
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        products_df.to_excel(writer, sheet_name=PRODUCT_SHEET, index=False)
        alias_df.to_excel(writer, sheet_name=SOURCE_SHEET, index=False)
        alias_v3_df.to_excel(writer, sheet_name=OUTPUT_ALIAS_SHEET, index=False)
        family_v3_df.to_excel(writer, sheet_name=OUTPUT_FAMILY_SHEET, index=False)
        presentations_df.to_excel(writer, sheet_name=PRESENTATION_SHEET, index=False)
        rules_df.to_excel(writer, sheet_name=RULE_SHEET, index=False)
        manual_seed_df.to_excel(writer, sheet_name=SEED_SHEET, index=False)
        impact_df.to_excel(writer, sheet_name=IMPACT_SHEET, index=False)

    print(f"Workbook generado: {output_path}")
    print(f"Filas impactadas por semillas: {total_matches}")
    print(impact_df.to_string(index=False))


if __name__ == "__main__":
    main()