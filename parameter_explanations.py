from __future__ import annotations


PARAMETER_EXPLANATION_TEMPLATES = {
    "thickness_m": {
        "summary": "Kalınlık, katmanın fiziksel kalınlığını ifade eder.",
        "impact": "Kalınlık artışı katman etkisini ve ısı geçiş davranışını değiştirebilir.",
    },
    "conductivity_w_per_mk": {
        "summary": "Iletkenlik, malzemenin ısıyı ne kadar kolay ilettiğini ifade eder.",
        "impact": "Iletkenlik arttığında ısı kaybı ve ısı kazancı davranışı belirgin biçimde etkilenebilir.",
    },
    "density_kg_per_m3": {
        "summary": "Yogunluk, malzemenin birim hacimdeki kütlesidir.",
        "impact": "Yogunluk değişimi ısıl kütle etkisini ve sıcaklık dalgalanmalarının zamansal yayılımını değiştirebilir.",
    },
    "specific_heat_j_per_kgk": {
        "summary": "Oz ısı, malzemenin sıcaklığını artırmak için gereken enerji kapasitesini anlatır.",
        "impact": "Oz ısı arttıkça malzemenin sıcaklığa tepkisi yavaşlayabilir ve termal konfor profili değişebilir.",
    },
    "thermal_resistance_m2k_per_w": {
        "summary": "Termal direnç, ısı geçişine karşı gösterilen direnci ifade eder.",
        "impact": "Termal direnç arttığında ısı kaybı azalabilir ve enerji performansı iyileşebilir.",
    },
}


def build_parameter_explanation(
    *,
    field_name: str,
    label: str,
    description: str,
    expected_impacts: tuple[str, ...] | list[str] | None = None,
) -> dict[str, str]:
    normalized_field = str(field_name or "").strip().lower()
    template = PARAMETER_EXPLANATION_TEMPLATES.get(normalized_field)

    if template:
        summary = str(template.get("summary", "")).strip()
        impact = str(template.get("impact", "")).strip()
    else:
        summary = str(description or "").strip() or (
            f"{label} parametresi ilgili yapı elemanının teknik davranışını etkiler."
        )
        impacts = [str(item).strip() for item in (expected_impacts or []) if str(item).strip()]
        if impacts:
            impact = (
                "Bu degisiklik su etkilerle iliskili olabilir: "
                + ", ".join(impacts[:3])
                + "."
            )
        else:
            impact = "Bu degisiklik katman etkisi, enerji performansi ve konfor sonucunu dolayli olarak etkileyebilir."

    return {
        "summary": summary,
        "impact": impact,
    }
