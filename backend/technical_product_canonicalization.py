import re
import unicodedata
from typing import Optional


def _normalize_text(value: Optional[str]) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9+/ ]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


GENERIC_FRAGMENT_TERMS = {
    "banos",
    "bano",
    "cocinas",
    "cocina",
    "catalizador",
    "severidad",
    "presion negativa",
    "presion",
    "negativa",
    "segun",
    "segun presion negativa y severidad",
    "acabado final",
    "acabado",
    "imprimante",
    "primer",
}


TECHNICAL_PRODUCT_RULES = [
    {"canonical_label": "Aquablock", "preferred_lookup_text": "aquablock ultra", "brand_filters": ["aquablock", "pintuco"], "aliases": ["aquablock", "aquablock ultra", "impermeabilizante cementicio", "aquablock / aquablock ultra", "bloqueador de humedad aquablock"]},
    {"canonical_label": "Sellamur", "preferred_lookup_text": "sellamur", "brand_filters": ["sellamur", "pintuco"], "aliases": ["sellamur"]},
    {"canonical_label": "Sellomax", "preferred_lookup_text": "sellomax", "brand_filters": ["sellomax", "pintuco"], "aliases": ["sellomax"]},
    {"canonical_label": "Koraza", "preferred_lookup_text": "koraza", "brand_filters": ["koraza", "pintuco"], "aliases": ["koraza", "impermeabilizante koraza", "koraza elastomerica", "koraza elastomerico"]},
    {"canonical_label": "Koraza Doble Vida", "preferred_lookup_text": "koraza doble vida", "brand_filters": ["koraza", "pintuco"], "aliases": ["koraza doble vida", "doble vida", "koraza 10 anos", "koraza 10 años"]},
    {"canonical_label": "Construcleaner", "preferred_lookup_text": "construcleaner", "brand_filters": ["construcleaner", "pintuco"], "aliases": ["construcleaner", "construcleaner limpiador desengrasante", "limpiador desengrasante construcleaner"]},
    {"canonical_label": "Siliconite 7", "preferred_lookup_text": "siliconite 7", "brand_filters": ["siliconite", "pintuco"], "aliases": ["siliconite 7", "siliconite", "hidrofugante siliconite"]},
    {"canonical_label": "Interseal gris RAL 7038", "preferred_lookup_text": "interseal gris ral 7038", "brand_filters": ["interseal", "international"], "aliases": ["interseal gris ral 7038", "interseal gris", "interseal 7038"]},
    {"canonical_label": "Interseal", "preferred_lookup_text": "interseal", "brand_filters": ["interseal", "international"], "aliases": ["interseal", "epoxica international", "epoxica akzonobel"]},
    {"canonical_label": "Intergard 2002", "preferred_lookup_text": "intergard 2002", "brand_filters": ["intergard", "international"], "aliases": ["intergard 2002"]},
    {"canonical_label": "Intergard 740", "preferred_lookup_text": "intergard 740", "brand_filters": ["intergard", "international"], "aliases": ["intergard 740"]},
    {"canonical_label": "Intergard", "preferred_lookup_text": "intergard", "brand_filters": ["intergard", "international"], "aliases": ["intergard", "primer international"]},
    {"canonical_label": "Interthane 990 + Catalizador", "preferred_lookup_text": "interthane 990", "brand_filters": ["interthane", "international"], "aliases": ["interthane 990 + catalizador", "interthane 990", "interthane", "poliuretano international"]},
    {"canonical_label": "Interfine", "preferred_lookup_text": "interfine", "brand_filters": ["interfine", "international"], "aliases": ["interfine"]},
    {"canonical_label": "Interchar", "preferred_lookup_text": "interchar", "brand_filters": ["interchar", "international"], "aliases": ["interchar", "intumescente interchar"]},
    {"canonical_label": "Barnex", "preferred_lookup_text": "barnex", "brand_filters": ["barnex", "pintuco"], "aliases": ["barnex"]},
    {"canonical_label": "Wood Stain", "preferred_lookup_text": "wood stain", "brand_filters": ["wood stain", "pintuco"], "aliases": ["wood stain", "tinte para madera exterior", "protector wood stain"]},
    {"canonical_label": "Poliuretano Alto Trafico 1550/1551", "preferred_lookup_text": "poliuretano alto trafico 1550", "brand_filters": ["pintuco"], "aliases": ["poliuretano alto trafico 1550/1551", "poliuretano alto trafico", "poliuretano 1550", "poliuretano 1551"]},
    {"canonical_label": "Pintuco Fill", "preferred_lookup_text": "pintuco fill", "brand_filters": ["pintuco fill", "pintuco"], "aliases": ["pintuco fill", "fill 7", "fill 12", "impermeabilizante pintuco fill"]},
    {"canonical_label": "Viniltex Baños y Cocinas", "preferred_lookup_text": "viniltex byc blanco 2001", "brand_filters": ["viniltex", "pintuco"], "aliases": ["viniltex baños y cocinas", "viniltex banos y cocinas", "viniltex baños", "viniltex banos", "banos y cocinas", "baños y cocinas", "viniltex byc", "pq viniltex byc", "viniltex byc sa", "viniltex byc sa blanco 2001", "pq viniltex byc sa blanco 2001 3 79l"]},
    {"canonical_label": "Viniltex Advanced", "preferred_lookup_text": "viniltex advanced", "brand_filters": ["viniltex", "pintuco"], "aliases": ["viniltex advanced", "viniltex adv", "viniltex premium"]},
    {"canonical_label": "Viniltex Ultralavable", "preferred_lookup_text": "viniltex ultralavable", "brand_filters": ["viniltex", "pintuco"], "aliases": ["viniltex ultralavable", "viniltex ultralav", "ultralavable"]},
    {"canonical_label": "Intervinil", "preferred_lookup_text": "intervinil", "brand_filters": ["intervinil", "pintuco"], "aliases": ["intervinil"]},
    {"canonical_label": "Pinturama", "preferred_lookup_text": "pinturama", "brand_filters": ["pinturama", "pintuco"], "aliases": ["pinturama"]},
    {"canonical_label": "Pintura Canchas", "preferred_lookup_text": "pintura canchas", "brand_filters": ["pintura canchas", "pintuco"], "aliases": ["pintura canchas", "pintura para canchas", "canchas"]},
    {"canonical_label": "Wash Primer", "preferred_lookup_text": "wash primer", "brand_filters": ["wash primer", "pintuco"], "aliases": ["wash primer", "washprimer", "primer de adherencia galvanizado"]},
    {"canonical_label": "Pintóxido", "preferred_lookup_text": "pintoxido", "brand_filters": ["pintoxido", "pintuco"], "aliases": ["pintoxido", "pintóxido", "convertidor oxido", "convertidor óxido"]},
    {"canonical_label": "Corrotec", "preferred_lookup_text": "corrotec", "brand_filters": ["corrotec", "pintuco"], "aliases": ["corrotec", "anticorrosivo corrotec"]},
    {"canonical_label": "Espuma de Poliuretano", "preferred_lookup_text": "espuma de poliuretano", "brand_filters": [], "aliases": ["espuma de poliuretano", "espuma expansiva", "espuma poliuretano"]},
    {"canonical_label": "Esmaltes Top Quality", "preferred_lookup_text": "top quality", "brand_filters": ["top quality", "pintuco"], "aliases": ["esmaltes top quality", "top quality", "esmalte top quality"]},
    {"canonical_label": "Pintucoat", "preferred_lookup_text": "pintucoat", "brand_filters": ["pintucoat", "pintuco"], "aliases": ["pintucoat", "epoxica pintuco", "epoxi pintuco"]},
    {"canonical_label": "Arena de Cuarzo ref 5891610", "preferred_lookup_text": "arena de cuarzo 5891610", "brand_filters": [], "aliases": ["arena de cuarzo ref 5891610", "arena de cuarzo 5891610", "cuarzo 5891610", "arena cuarzo"]},
    {"canonical_label": "Pintulux 3 en 1", "preferred_lookup_text": "pintulux 3 en 1", "brand_filters": ["pintulux", "pintuco"], "aliases": ["pintulux 3 en 1", "pintulux 3en1", "pintulux"]},
    {"canonical_label": "Altas Temperaturas", "preferred_lookup_text": "altas temperaturas", "brand_filters": ["pintuco"], "aliases": ["altas temperaturas", "alta temperatura", "pintura altas temperaturas"]},

    # === REGLAS GENERADAS DESDE CSV VALIDADO POR USUARIO (136 reglas) ===
    {"canonical_label": "AJUSTADOR PARA EPOXICAS 21209", "preferred_lookup_text": "AJUSTADOR PINT EPOX BOTELLA 209", "brand_filters": [], "aliases": ["ajustador para epoxicas 21209", "ajustador para epoxicas"]},
    {"canonical_label": "AJUSTADOR XILOL 21204", "preferred_lookup_text": "AJUSTADOR MEDIO TRAFICO BOTELLA 204", "brand_filters": [], "aliases": ["ajustador xilol 21204", "ajustador xilol"]},
    {"canonical_label": "THINNER CENTRAL DE DISOLVENTES", "preferred_lookup_text": "THINNER CORRIENTE BOTELLA", "brand_filters": [], "aliases": ["thinner central de disolventes"]},
    {"canonical_label": "BALL", "preferred_lookup_text": "BALL A40S BAÑO SILVER", "brand_filters": [], "aliases": ["ball"]},
    {"canonical_label": "BELL WOOD", "preferred_lookup_text": "BELL WOOD GOLD A40S BAÑO", "brand_filters": [], "aliases": ["bell wood"]},
    {"canonical_label": "C999", "preferred_lookup_text": "CERRADURA SOBREPONER C999 DERC", "brand_filters": [], "aliases": ["c999"]},
    {"canonical_label": "C999 ULTRA", "preferred_lookup_text": "CERRADURA C999 ULTRA IZQU", "brand_filters": [], "aliases": ["c999 ultra"]},
    {"canonical_label": "JUPITER", "preferred_lookup_text": "JUPITER CROMADO MATE A40S BAÑO", "brand_filters": [], "aliases": ["jupiter"]},
    {"canonical_label": "SATURNO", "preferred_lookup_text": "SATURNO SATIN NIQUEL A40S BAÑO", "brand_filters": [], "aliases": ["saturno"]},
    {"canonical_label": "SUPRA INAFER", "preferred_lookup_text": "CERRADURA SUPRA DERECHA", "brand_filters": [], "aliases": ["supra inafer"]},
    {"canonical_label": "B 360", "preferred_lookup_text": "CERROJO B360 CROMADO MATE LL-M SEGUREX", "brand_filters": [], "aliases": ["b 360"]},
    {"canonical_label": "B 362", "preferred_lookup_text": "CERROJO B362 CROMADO MATE LL-LL SEGUREX", "brand_filters": [], "aliases": ["b 362"]},
    {"canonical_label": "MEGA", "preferred_lookup_text": "CERRADURA SOBREPONER MEGA DERC", "brand_filters": [], "aliases": ["mega"]},
    {"canonical_label": "SEALER F100 UFA550 UFA551 ES", "preferred_lookup_text": "SEALER F100 UFA550/20L/AA7", "brand_filters": [], "aliases": ["sealer f100 ufa550 ufa551 es"]},
    {"canonical_label": "ACRILICA BASE AGUA UDA600 ES", "preferred_lookup_text": "ACRILICA BASE AGUA UDA600/3.7L/AA7", "brand_filters": [], "aliases": ["acrilica base agua uda600 es"]},
    {"canonical_label": "ACRILICA MANTENIMIENTO ES", "preferred_lookup_text": "ACRILICA MANT 13883 11Z028/3.7L/AA7", "brand_filters": [], "aliases": ["acrilica mantenimiento es"]},
    {"canonical_label": "ARENA QUARZO G300N UFA850 ES", "preferred_lookup_text": "ARENA QUARZO G300N UFA850/25KG/AA7", "brand_filters": [], "aliases": ["arena quarzo g300n ufa850 es"]},
    {"canonical_label": "EPOXI POLIAMIDA ES", "preferred_lookup_text": "EPOXI POLIAMIDA 13243 UFA407/3.7L/AA7", "brand_filters": [], "aliases": ["epoxi poliamida es"]},
    {"canonical_label": "EPOXY PRIMER 10050 UEA301 UEA302 ES", "preferred_lookup_text": "EPOXY PRIMER 10050 UEA301/3.7L/AA7", "brand_filters": [], "aliases": ["epoxy primer 10050 uea301 uea302 es", "epoxy primer  uea301 uea302 es"]},
    {"canonical_label": "EPOXY PRIMER 50RS UEA400 UEA401 UEA402 ES", "preferred_lookup_text": "EPOXY PRIMER 50RS UEA400/3.7L/AA7", "brand_filters": [], "aliases": ["epoxy primer 50rs uea400 uea401 uea402 es"]},
    {"canonical_label": "ESMALTE MAQUINARIA 11271 UFA102 ES", "preferred_lookup_text": "ESMALTE MAQUINARIA 11271 UFA102/3.7L/AA7", "brand_filters": [], "aliases": ["esmalte maquinaria 11271 ufa102 es", "esmalte maquinaria  ufa102 es"]},
    {"canonical_label": "ACUALUX", "preferred_lookup_text": "PQ PINTULUX ACUALUX SB BLANCO 1111 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco acualux", "acualux"]},
    {"canonical_label": "CATALIZADOR E 40", "preferred_lookup_text": "MEG HARDENER UNIVERSAL E40 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco catalizador e 40", "catalizador e 40"]},
    {"canonical_label": "CONCENTRADOS", "preferred_lookup_text": "PQ COLORANTE BAJO VOC AMARIL MED 0.95L", "brand_filters": ["pintuco"], "aliases": ["pintuco concentrados", "concentrados"]},
    {"canonical_label": "DOMESTICO", "preferred_lookup_text": "PQ DOMESTICO BR BLANCO P-11 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco domestico", "domestico"]},
    {"canonical_label": "EPOXIPOLIAMIDA", "preferred_lookup_text": "EPOXI POLIAMIDA 13243 UFA407/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco epoxipoliamida", "epoxipoliamida"]},
    {"canonical_label": "ESTUCOMASTIC 2 EN 1", "preferred_lookup_text": "PQ ESTUCOMAST BLANCO 18070 18.93L 27K", "brand_filters": ["pintuco"], "aliases": ["pintuco estucomastic 2 en 1", "estucomastic 2 en 1"]},
    {"canonical_label": "FLEX", "preferred_lookup_text": "SELLADOR POLIURETANO PU40 BLANCO 310ML/3", "brand_filters": ["pintuco"], "aliases": ["pintuco flex", "flex"]},
    {"canonical_label": "IMPRIMAX", "preferred_lookup_text": "PQ IMPRIMAX BLANCO 3501 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco imprimax", "imprimax"]},
    {"canonical_label": "MONTANA 94", "preferred_lookup_text": "ZP MONTANA 94 MAT NEGRO EX0149011M 0.4L", "brand_filters": ["pintuco"], "aliases": ["pintuco montana 94", "montana 94"]},
    {"canonical_label": "PINTULACA", "preferred_lookup_text": "MEG PINTULACA BLANCO 7519 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintulaca", "pintulaca"]},
    {"canonical_label": "PLASTICO EN FRIO EN LLANA", "preferred_lookup_text": "P7 PLASTICO EN FRIO AMARILLO 13762 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco plastico en frio en llana", "plastico en frio en llana"]},
    {"canonical_label": "PRIMER 2K 5001", "preferred_lookup_text": "BASE 2K GRIS MEDIO 5001 MEG AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco primer 2k 5001", "pintuco primer 2k", "primer 2k 5001"]},
    {"canonical_label": "REMOVEDOR 1020", "preferred_lookup_text": "MEG REMOVEDOR DE PINTURAS 1020 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco removedor 1020", "pintuco removedor", "removedor 1020"]},
    {"canonical_label": "REVOMASTIC", "preferred_lookup_text": "P7 REVOQUE PLAST BLANCO 17091 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco revomastic", "revomastic"]},
    {"canonical_label": "SILICONA NEUTRA", "preferred_lookup_text": "SILICONA NEUTRA POLICARBONATO 280 ML", "brand_filters": ["pintuco"], "aliases": ["pintuco silicona neutra", "silicona neutra"]},
    {"canonical_label": "SILICONA ULTRA 3 EN 1", "preferred_lookup_text": "SILICONA BAÑO Y COCINA BLANCA 280ML", "brand_filters": ["pintuco"], "aliases": ["pintuco silicona ultra 3 en 1", "silicona ultra 3 en 1"]},
    {"canonical_label": "THINNER P 502", "preferred_lookup_text": "THINNER UNIVERSAL P502 MEG AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco thinner p 502", "thinner p 502"]},
    {"canonical_label": "VARETA", "preferred_lookup_text": "MH VARETA MAT NEGRO 10005-5001 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco vareta", "vareta"]},
    {"canonical_label": "VINILUX 2 EN 1", "preferred_lookup_text": "IQ VINILUX MAT BLANCO 2022155 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco vinilux 2 en 1", "vinilux 2 en 1"]},
    {"canonical_label": "PRIMER EPOXY 10046", "preferred_lookup_text": "EPOXY PRIMER 10046 UEA250/3.7L/AA7", "brand_filters": [], "aliases": ["primer epoxy 10046", "primer epoxy"]},
    {"canonical_label": "REMOVEDOR PINTUCO 1020", "preferred_lookup_text": "MEG REMOVEDOR DE PINTURAS 1020 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["removedor pintuco 1020", "removedor pintuco"]},
    {"canonical_label": "BROCHA PROFESIONAL PLASTICO BLANCA PINTUCO", "preferred_lookup_text": "BROCHA PROF PLASTICO BCA 2 PULG PINTUCO", "brand_filters": ["pintuco"], "aliases": ["brocha profesional plastico blanca pintuco"]},
    {"canonical_label": "EPOXICA BASE AGUA PINTUCO", "preferred_lookup_text": "ACRILICA BASE AGUA UDA600/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["epoxica base agua pintuco"]},
    {"canonical_label": "ACRILICA PARA MANTENIMIENTO", "preferred_lookup_text": "ACRILICA MANT 13883 11Z028/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco acrilica para mantenimiento", "acrilica para mantenimiento"]},
    {"canonical_label": "ACRILTEX VINILTEX", "preferred_lookup_text": "PQ VINILTEX ACRILTEX SA BLAN 2761 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco acriltex viniltex", "acriltex viniltex"]},
    {"canonical_label": "AEROCOLOR ELECTROGASODOMESTICOS", "preferred_lookup_text": "PQ AEROCOLOR ELECTROGAS MAT BLANCO 0.3L", "brand_filters": ["pintuco"], "aliases": ["pintuco aerocolor electrogasodomesticos", "aerocolor electrogasodomesticos"]},
    {"canonical_label": "AEROCOLOR MULTISUPERFICIE", "preferred_lookup_text": "PQ AEROCOLOR MULTISU BR BLANCO 0.3L", "brand_filters": ["pintuco"], "aliases": ["pintuco aerocolor multisuperficie", "aerocolor multisuperficie"]},
    {"canonical_label": "AEROCOLOR PARA RINES", "preferred_lookup_text": "PQ AEROCOLOR RINES BR ALUMINIO 0.3L", "brand_filters": ["pintuco"], "aliases": ["pintuco aerocolor para rines", "aerocolor para rines"]},
    {"canonical_label": "AEROSOL TEKBOND", "preferred_lookup_text": "PINTURA EN AEROSOL GRAL PLATINA 350 ML", "brand_filters": ["pintuco"], "aliases": ["pintuco aerosol tekbond", "aerosol tekbond"]},
    {"canonical_label": "AJUSTADOR AROMATICO 21204", "preferred_lookup_text": "AJUSTADOR MEDIO TRAFICO BOTELLA 204", "brand_filters": ["pintuco"], "aliases": ["pintuco ajustador aromatico 21204", "pintuco ajustador aromatico", "ajustador aromatico 21204"]},
    {"canonical_label": "AJUSTADOR EPOXICO 21209", "preferred_lookup_text": "MPY AJUSTADOR 21209 UFA153/20L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco ajustador epoxico 21209", "pintuco ajustador epoxico", "ajustador epoxico 21209"]},
    {"canonical_label": "ALUMINIO LIQUIDO ECP 100", "preferred_lookup_text": "PQ CORROTEC ALUMINIO BR ECP100 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco aluminio liquido ecp 100", "aluminio liquido ecp 100"]},
    {"canonical_label": "ANTICORROSIVO AMARILLO 505", "preferred_lookup_text": "5890865", "brand_filters": ["pintuco"], "aliases": ["pintuco anticorrosivo amarillo 505", "anticorrosivo amarillo 505"]},
    {"canonical_label": "ANTICORROSIVO INDUSTRIAL 210003", "preferred_lookup_text": "5891082", "brand_filters": ["pintuco"], "aliases": ["pintuco anticorrosivo industrial 210003", "pintuco anticorrosivo industrial", "anticorrosivo industrial 210003"]},
    {"canonical_label": "ANTICORROSIVO ROJO 10050 545", "preferred_lookup_text": "EPOXY PRIMER 10050 UEA301/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco anticorrosivo rojo 10050 545", "pintuco anticorrosivo rojo  545", "anticorrosivo rojo 10050 545"]},
    {"canonical_label": "ARENA DE QUARZO G300N", "preferred_lookup_text": "ARENA QUARZO G300N UFA850/25KG/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco arena de quarzo g300n", "arena de quarzo g300n"]},
    {"canonical_label": "ASEPSIA ULTRA", "preferred_lookup_text": "5893351", "brand_filters": ["pintuco"], "aliases": ["pintuco asepsia ultra", "asepsia ultra"]},
    {"canonical_label": "BARNIZ CLEAR MATE 9450", "preferred_lookup_text": "MEG CLEAR MATE 2K 9450 AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco barniz clear mate 9450", "pintuco barniz clear mate", "barniz clear mate 9450"]},
    {"canonical_label": "BARNIZ CRISTAL CLEAR 9400", "preferred_lookup_text": "MEG CRYSTAL CLEAR 9400 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco barniz cristal clear 9400", "pintuco barniz cristal clear", "barniz cristal clear 9400"]},
    {"canonical_label": "BARNIZ SD1", "preferred_lookup_text": "MH BARNIZ BR INCOLORO SD-1 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco barniz sd1", "barniz sd1"]},
    {"canonical_label": "CLEAR RFU 5500", "preferred_lookup_text": "MEG CLEAR HS 2K RFU5500 AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco clear rfu 5500", "pintuco clear rfu", "clear rfu 5500"]},
    {"canonical_label": "DESMOLDANTE GLASS PRIME", "preferred_lookup_text": "20002529", "brand_filters": ["pintuco"], "aliases": ["pintuco desmoldante glass prime", "desmoldante glass prime"]},
    {"canonical_label": "DESMOLDANTE GLASS SUPREME", "preferred_lookup_text": "20002528", "brand_filters": ["pintuco"], "aliases": ["pintuco desmoldante glass supreme", "desmoldante glass supreme"]},
    {"canonical_label": "DESMOLDANTE GLASST PRIME", "preferred_lookup_text": "20002529", "brand_filters": ["pintuco"], "aliases": ["pintuco desmoldante glasst prime", "desmoldante glasst prime"]},
    {"canonical_label": "DRYWALL TIPO 2", "preferred_lookup_text": "P7 DRYWALL TIPO 2 BLANCO 3780 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco drywall tipo 2", "drywall tipo 2"]},
    {"canonical_label": "EPOXICA BASE AGUA", "preferred_lookup_text": "P7 ASEPSIA ULTRA BLANCO 27081 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco epoxica base agua", "epoxica base agua"]},
    {"canonical_label": "EQUIPOS GRACO", "preferred_lookup_text": "WAGNER CONTROL PRO 190", "brand_filters": ["pintuco"], "aliases": ["pintuco equipos graco", "equipos graco"]},
    {"canonical_label": "ESGRAFIADO PREMIUN GRANIPLAST", "preferred_lookup_text": "PQ ESGRAF MAT BLANC 30401 15.14L 30K", "brand_filters": ["pintuco", "graniplast"], "aliases": ["pintuco esgrafiado premiun graniplast", "esgrafiado premiun graniplast"]},
    {"canonical_label": "ESGRAFIADO STANDARD GRANIPLAST", "preferred_lookup_text": "PQ ESGRAFIADO EST MAT 40401 18.93L 30K", "brand_filters": ["pintuco", "graniplast"], "aliases": ["pintuco esgrafiado standard graniplast", "esgrafiado standard graniplast"]},
    {"canonical_label": "ESTUCO ACRILICO EXTERIOR", "preferred_lookup_text": "PQ ESTUCO PROF EXT BL 27060 18.93L 30K", "brand_filters": ["pintuco"], "aliases": ["pintuco estuco acrilico exterior", "estuco acrilico exterior", "estuco acrilico para exterior", "estuco para exterior y humedad", "estuco profesional exterior", "pintuco estuco profesional exterior", "estuco prof ext", "estuco prof ext blanco", "pq estuco prof ext bl 27060 18.93l 30k"]},
    {"canonical_label": "ESTUCO PROFESIONAL 2 EN 1", "preferred_lookup_text": "PQ ESTUCOMAST BLANCO 18070 18.93L 27K", "brand_filters": ["pintuco"], "aliases": ["pintuco estuco profesional 2 en 1", "estuco profesional 2 en 1"]},
    {"canonical_label": "ESTUCO PROFESIONAL OBRA", "preferred_lookup_text": "PQ ESTUCOMAST BLANCO 18070 18.93L 27K", "brand_filters": ["pintuco"], "aliases": ["pintuco estuco profesional obra", "estuco profesional obra"]},
    {"canonical_label": "ESTUCOR LISTO", "preferred_lookup_text": "ESTUCOR BULTO *25 KL LISTO", "brand_filters": ["pintuco"], "aliases": ["pintuco estucor listo", "estucor listo"]},
    {"canonical_label": "ESTUCOR MOLDURAS", "preferred_lookup_text": "ESTUCOR BULTO *25 KLS MOLDURA", "brand_filters": ["pintuco"], "aliases": ["pintuco estucor molduras", "estucor molduras"]},
    {"canonical_label": "FLEX PROFESIONAL", "preferred_lookup_text": "SELLADOR POLIURETANO PUFIX BLANCO 387G", "brand_filters": ["pintuco"], "aliases": ["pintuco flex profesional", "flex profesional"]},
    {"canonical_label": "FT SELLADOR ACRILICO", "preferred_lookup_text": "ADHESIVO ACRILICO DE JUNTAS BLANCO 425 G", "brand_filters": ["pintuco"], "aliases": ["pintuco ft sellador acrilico", "ft sellador acrilico"]},
    {"canonical_label": "FTP INVECRYL 500 DOCX", "preferred_lookup_text": "INVECRYL 500 3KG", "brand_filters": ["pintuco"], "aliases": ["pintuco ftp invecryl 500 docx", "ftp invecryl 500 docx"]},
    {"canonical_label": "GRANIACRYL PREMIUM GRANIPLAST", "preferred_lookup_text": "PQ GRANIACRYL MAT BLANC 30601 15.14L 30K", "brand_filters": ["pintuco", "graniplast"], "aliases": ["pintuco graniacryl premium graniplast", "graniacryl premium graniplast"]},
    {"canonical_label": "IMPADOC LISTO", "preferred_lookup_text": "IMPADOC BULTO", "brand_filters": ["pintuco"], "aliases": ["pintuco impadoc listo", "impadoc listo"]},
    {"canonical_label": "IMPRIMANTE ACRILICO TRAFICO", "preferred_lookup_text": "P7 PINTUTRAF IMPRIMAN NEGRO 13759 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco imprimante acrilico trafico", "imprimante acrilico trafico"]},
    {"canonical_label": "MADECTEC SELLADOR NITRO", "preferred_lookup_text": "MH SISTEMA NITRO INCOLORO 7204 0.95L", "brand_filters": ["pintuco"], "aliases": ["pintuco madectec sellador nitro", "madectec sellador nitro"]},
    {"canonical_label": "MADETEC BASE AGUA", "preferred_lookup_text": "MH VITRIFLEX SM 2130 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco madetec base agua", "madetec base agua"]},
    {"canonical_label": "MADETEC VITRIFLEX PARTE A", "preferred_lookup_text": "MH VITRIFLEX SM 2130 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco madetec vitriflex parte a", "madetec vitriflex parte a"]},
    {"canonical_label": "MADETEC VITRIFLEX PARTE B", "preferred_lookup_text": "MH VITRIFLEX SM 2130 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco madetec vitriflex parte b", "madetec vitriflex parte b"]},
    {"canonical_label": "MASILLA DURETAN 19167", "preferred_lookup_text": "MEG MASILLA PS BLANCA 19167 AC 6.5KG", "brand_filters": ["pintuco"], "aliases": ["pintuco masilla duretan 19167", "pintuco masilla duretan", "masilla duretan 19167"]},
    {"canonical_label": "MASILLA P2500", "preferred_lookup_text": "MEG MASILLA POLIESTER P2500 AC 1.1KG", "brand_filters": ["pintuco"], "aliases": ["pintuco masilla p2500", "masilla p2500"]},
    {"canonical_label": "MASILLA POLIESTER P1500", "preferred_lookup_text": "MEG MASILLA POLIESTER P1500 AC 0.75KG", "brand_filters": ["pintuco"], "aliases": ["pintuco masilla poliester p1500", "masilla poliester p1500"]},
    {"canonical_label": "MONTANA HARDCORE", "preferred_lookup_text": "ZP MONTANA HC BR NEGRO EX014H9011 0.4L", "brand_filters": ["pintuco"], "aliases": ["pintuco montana hardcore", "montana hardcore"]},
    {"canonical_label": "PASTA PULIDORA 120025", "preferred_lookup_text": "MEG PASTA PULIDOR BLANCO 120025 AC 0.70L", "brand_filters": ["pintuco"], "aliases": ["pintuco pasta pulidora 120025", "pintuco pasta pulidora", "pasta pulidora 120025"]},
    {"canonical_label": "PASTA PULIDORA CREMA 4040", "preferred_lookup_text": "MEG PASTA PULIDORA CREMA 4040 AC 0.70L", "brand_filters": ["pintuco"], "aliases": ["pintuco pasta pulidora crema 4040", "pintuco pasta pulidora crema", "pasta pulidora crema 4040"]},
    {"canonical_label": "PERMEX BASE AGUA 13421", "preferred_lookup_text": "5891281", "brand_filters": ["pintuco"], "aliases": ["pintuco permex base agua 13421", "pintuco permex base agua", "permex base agua 13421"]},
    {"canonical_label": "PINTULAC NEGRO MATIZ 7589", "preferred_lookup_text": "MEG PINTULACA NEGRO MATIZ 7589 AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintulac negro matiz 7589", "pintuco pintulac negro matiz", "pintulac negro matiz 7589"]},
    {"canonical_label": "PINTURA ANTIGRAFITTI", "preferred_lookup_text": "P7 SET PINTURA ANTIGRAFFITI 2024 3.79 L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura antigrafitti", "pintura antigrafitti"]},
    {"canonical_label": "PINTURA ENTUMESENTE", "preferred_lookup_text": "INTERCHAR 2060 HFA060/20L/EU", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura entumesente", "pintura entumesente"]},
    {"canonical_label": "POLIURETANO SERIE 600 BRILLANTE", "preferred_lookup_text": "MEG PU S605 NEGRO AZULOSO AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco poliuretano serie 600 brillante", "poliuretano serie 600 brillante"]},
    {"canonical_label": "PRIMER ALQUIDICO 210003", "preferred_lookup_text": "5891082", "brand_filters": ["pintuco"], "aliases": ["pintuco primer alquidico 210003", "pintuco primer alquidico", "primer alquidico 210003"]},
    {"canonical_label": "PRIMER EPOXICO 10046", "preferred_lookup_text": "EPOXY PRIMER 10046 UEA250/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco primer epoxico 10046", "pintuco primer epoxico", "primer epoxico 10046"]},
    {"canonical_label": "PRIMER PARA PLASTICOS", "preferred_lookup_text": "MEG PRIMER PARA PLASTICOS 28600 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco primer para plasticos", "primer para plasticos"]},
    {"canonical_label": "PRIMER PARA PLASTICOS 28600", "preferred_lookup_text": "MEG PRIMER PARA PLASTICOS 28600 AC 0.94L", "brand_filters": ["pintuco"], "aliases": ["pintuco primer para plasticos 28600", "pintuco primer para plasticos", "primer para plasticos 28600"]},
    {"canonical_label": "PU MATE SERIE 600 ACT", "preferred_lookup_text": "MEG PU MG6004 BLANCO MIX AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco pu mate serie 600 act", "pu mate serie 600 act"]},
    {"canonical_label": "PUFIX BLANCO", "preferred_lookup_text": "SELLADOR POLIURETANO PUFIX BLANCO 387G", "brand_filters": ["pintuco"], "aliases": ["pintuco pufix blanco", "pufix blanco"]},
    {"canonical_label": "QUARZ G300N", "preferred_lookup_text": "ARENA QUARZO G300N UFA850/25KG/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco quarz g300n", "quarz g300n"]},
    {"canonical_label": "SEALER F100", "preferred_lookup_text": "SEALER F100 UFA550/20L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco sealer f100", "sealer f100"]},
    {"canonical_label": "SELLADOR ACRILICO", "preferred_lookup_text": "ADHESIVO ACRILICO DE JUNTAS BLANCO 425 G", "brand_filters": ["pintuco"], "aliases": ["pintuco sellador acrilico", "sellador acrilico"]},
    {"canonical_label": "SUPER GRIP", "preferred_lookup_text": "P7 SUPER GRIP ANTIDESLIZANT 13779 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco super grip", "super grip"]},
    {"canonical_label": "SUPER GRIP ANTIDESLIZANTE", "preferred_lookup_text": "P7 SUPER GRIP ANTIDESLIZANT 13779 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco super grip antideslizante", "super grip antideslizante"]},
    {"canonical_label": "TELA DE REFUERZO", "preferred_lookup_text": "PQ TELA DE REFUERZO 2800 10 METRO", "brand_filters": ["pintuco"], "aliases": ["pintuco tela de refuerzo", "tela de refuerzo"]},
    {"canonical_label": "TEXACRYL ACROLATEX", "preferred_lookup_text": "PQ ACROLATEX 50 3508 4K", "brand_filters": ["pintuco"], "aliases": ["pintuco texacryl acrolatex", "texacryl acrolatex"]},
    {"canonical_label": "THINNER CORRIENTE 21219", "preferred_lookup_text": "THINNER CORRIENTE GALON", "brand_filters": ["pintuco"], "aliases": ["pintuco thinner corriente 21219", "pintuco thinner corriente", "thinner corriente 21219"]},
    {"canonical_label": "THINNER INDUSOL", "preferred_lookup_text": "THINNER CORRIENTE GALON", "brand_filters": ["pintuco"], "aliases": ["pintuco thinner indusol", "thinner indusol"]},
    {"canonical_label": "THINNER POLIURETANO 21050", "preferred_lookup_text": "MPY THINNER 21050 UFA151/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco thinner poliuretano 21050", "pintuco thinner poliuretano", "thinner poliuretano 21050"]},
    {"canonical_label": "TINTE PARA MADERA", "preferred_lookup_text": "MH TINTES PARA MADERA CAOBA 7437 0.95L", "brand_filters": ["pintuco"], "aliases": ["pintuco tinte para madera", "tinte para madera"]},
    {"canonical_label": "VINIL LATEX TERINSA", "preferred_lookup_text": "TE VINIL LATEX MAT BLANCO 65232 18.93L", "brand_filters": ["pintuco", "terinsa"], "aliases": ["pintuco vinil latex terinsa", "vinil latex terinsa"]},
    {"canonical_label": "VINIL MAX TERINSA", "preferred_lookup_text": "TE VINIL MAX MAT BLANCO 35232 18.93L", "brand_filters": ["pintuco", "terinsa"], "aliases": ["pintuco vinil max terinsa", "vinil max terinsa"]},
    {"canonical_label": "VINIL PLUS TERINSA", "preferred_lookup_text": "TE VINIL PLUS MAT BLANCO 95232 3.79L", "brand_filters": ["pintuco", "terinsa"], "aliases": ["pintuco vinil plus terinsa", "vinil plus terinsa"]},
    {"canonical_label": "VINILICO TIPO 1", "preferred_lookup_text": "VINILO STANDAR T1 MAT WHITE 1699 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco vinilico tipo 1", "vinilico tipo 1"]},
    {"canonical_label": "VINILO TIPO 1 CONSTRUCTOR", "preferred_lookup_text": "VINILO STANDAR T1 MAT WHITE 1699 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco vinilo tipo 1 constructor", "vinilo tipo 1 constructor"]},
    {"canonical_label": "VINILTEX BIO CUIDADO", "preferred_lookup_text": "PQ VTEX BIOCUIDADO MAT BLANC 1901 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco viniltex bio cuidado", "viniltex bio cuidado"]},
    {"canonical_label": "VINILTEX PRO 450", "preferred_lookup_text": "P7 VINILTEX PRO 450 MAT BLAN 1601 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco viniltex pro 450", "viniltex pro 450"]},
    {"canonical_label": "VINILTEX PRO 650", "preferred_lookup_text": "P7 VINILTEX PRO 650 MAT BLAN 1600 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco viniltex pro 650", "viniltex pro 650"]},
    {"canonical_label": "VITRIFLEX BASE AGUA", "preferred_lookup_text": "MH VITRIFLEX SM 2130 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco vitriflex base agua", "vitriflex base agua"]},
    {"canonical_label": "AJUSTADOR ACRILICAS CAUCHO CLORADO 21121", "preferred_lookup_text": "AJUSTADOR PARA PINTUTRAFICO 21121 BOTELL", "brand_filters": ["pintuco"], "aliases": ["pintuco ajustador acrilicas caucho clorado 21121", "pintuco ajustador acrilicas caucho clorado", "ajustador acrilicas caucho clorado 21121"]},
    {"canonical_label": "ESMALTE PARA PROTECCION MAQUINARIA", "preferred_lookup_text": "ESMALTE MAQUINARIA 11271 UFA102/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco esmalte para proteccion maquinaria", "esmalte para proteccion maquinaria"]},
    {"canonical_label": "FDC ANTICORROSIVO VERDE OLIVA 513", "preferred_lookup_text": "MEG PRIMER ANTIC VERDE OLIV 513 AC 3.78L", "brand_filters": ["pintuco"], "aliases": ["pintuco fdc anticorrosivo verde oliva 513", "fdc anticorrosivo verde oliva 513"]},
    {"canonical_label": "IMPRIMANTE PARA TRAFICO ACRILICO NEGRO 10255632", "preferred_lookup_text": "P7 PINTUTRAF IMPRIMAN NEGRO 13759 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco imprimante para trafico acrilico negro 10255632", "imprimante para trafico acrilico negro 10255632"]},
    {"canonical_label": "LACA MULTIUSOS AEROCOLOR GENERICA", "preferred_lookup_text": "PQ AEROCOLOR MULTISU BR NEGRO 0.3L", "brand_filters": ["pintuco"], "aliases": ["pintuco laca multiusos aerocolor generica", "laca multiusos aerocolor generica"]},
    {"canonical_label": "PINTURA ACRILICA ALTA ASEPSIA", "preferred_lookup_text": "P7 ASEPSIA BLANCO 27580 18.93L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura acrilica alta asepsia", "pintura acrilica alta asepsia"]},
    {"canonical_label": "PINTURA ACRILICA PARA MANTENIMIENTO", "preferred_lookup_text": "ACRILICA MANT 13884 11Z651/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura acrilica para mantenimiento", "pintura acrilica para mantenimiento"]},
    {"canonical_label": "PINTURA EPOXICA BASE SOLVENTE", "preferred_lookup_text": "P7 KIT EPOXICA B SOLVENT BLA 13580 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura epoxica base solvente", "pintura epoxica base solvente"]},
    {"canonical_label": "PINTURA EPOXICA PARA CONCRETO", "preferred_lookup_text": "P7 KIT EPOXICA B SOLVENT BLA 13580 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintura epoxica para concreto", "pintura epoxica para concreto"]},
    {"canonical_label": "PINTUTRAFICO ACRILICO BASE SOLVENTE", "preferred_lookup_text": "P7 PINTUTRAF BS AMARILLO 13755-659 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintutrafico acrilico base solvente", "pintutrafico acrilico base solvente"]},
    {"canonical_label": "PINTUTRAFICO ACRILICO BASE SOLVENTE 13754 55 56", "preferred_lookup_text": "P7 PINTUTRAF BS BLANCO 13754-653 3.79L", "brand_filters": ["pintuco"], "aliases": ["pintuco pintutrafico acrilico base solvente 13754 55 56", "pintuco pintutrafico acrilico base solvente  55 56", "pintutrafico acrilico base solvente 13754 55 56"]},
    {"canonical_label": "PRIMER EPOXI RAPIDO SECADO 50RS", "preferred_lookup_text": "EPOXY PRIMER 50RS UEA400/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco primer epoxi rapido secado 50rs", "primer epoxi rapido secado 50rs"]},
    {"canonical_label": "PRIMER EPOXICO DE RAPIDO SECADO GRIS", "preferred_lookup_text": "EPOXY PRIMER 50RS UEA400/3.7L/AA7", "brand_filters": ["pintuco"], "aliases": ["pintuco primer epoxico de rapido secado gris", "primer epoxico de rapido secado gris"]},
    {"canonical_label": "INTERNATIONAL 21204", "preferred_lookup_text": "AJUSTADOR MEDIO TRAFICO BOTELLA 204", "brand_filters": [], "aliases": ["international 21204", "international"]},
]


def get_technical_product_universe() -> list[dict]:
    return [{"canonical_label": rule["canonical_label"], "preferred_lookup_text": rule["preferred_lookup_text"], "brand_filters": list(rule.get("brand_filters") or []), "aliases": list(rule.get("aliases") or [])} for rule in TECHNICAL_PRODUCT_RULES]


def canonicalize_technical_product_term(product_text: Optional[str]) -> Optional[dict]:
    normalized = _normalize_text(product_text)
    if not normalized or normalized in GENERIC_FRAGMENT_TERMS:
        return None
    best_rule = None
    best_alias = ""
    for rule in TECHNICAL_PRODUCT_RULES:
        for alias in rule.get("aliases") or []:
            alias_normalized = _normalize_text(alias)
            if not alias_normalized:
                continue
            if normalized == alias_normalized or alias_normalized in normalized:
                if len(alias_normalized) > len(best_alias):
                    best_alias = alias_normalized
                    best_rule = rule
    if not best_rule:
        return None
    return {
        "canonical_label": best_rule["canonical_label"],
        "preferred_lookup_text": best_rule["preferred_lookup_text"],
        "brand_filters": list(best_rule.get("brand_filters") or []),
        "matched_alias": best_alias,
        "input_text": str(product_text or "").strip(),
    }


def canonicalize_technical_product_list(values: list[str]) -> list[str]:
    results = []
    seen = set()
    for value in values or []:
        resolved = canonicalize_technical_product_term(value)
        label = (resolved or {}).get("canonical_label") or str(value or "").strip()
        normalized_label = _normalize_text(label)
        if not normalized_label or normalized_label in GENERIC_FRAGMENT_TERMS or normalized_label in seen:
            continue
        seen.add(normalized_label)
        results.append(label)
    return results