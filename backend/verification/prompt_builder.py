"""
Moso AI — Anti-Hallucination & Factual Grounding Prompt Builder
Generates instructions for the model to acknowledge uncertainty, prevent
fabricated quotations/references, and enforce evidence grounding.
"""

from typing import Dict, Any, List
from .classifier import VerificationIntent


def build_verification_system_prompt(
    intent: VerificationIntent,
    retrieved_material: Dict[str, Any],
    project_instructions: str = ""
) -> str:
    """
    Build targeted instructions for the inference model to adhere to factual rigor,
    quotation verification, and appropriate abstention.
    """
    directives = []

    directives.append(
        "CORE FACTUAL VERIFICATION RULES:\n"
        "1. DO NOT fabricate quotations, citations, journal articles, DOIs, page numbers, or statistics.\n"
        "2. When source text or verified references are provided, answer using that exact evidence.\n"
        "3. When requested evidence is absent from provided sources, explicitly state: "
        "'The attached document(s) do not contain sufficient evidence to answer this question.' "
        "or acknowledge that the claim cannot be independently verified.\n"
        "4. Clearly distinguish exact quotations from summaries and paraphrases.\n"
        "5. Format all mathematical equations, scientific formulas, and symbols in valid LaTeX: "
        "use \\( ... \\) for inline math and \\[ ... \\] for standalone equations."
    )

    # Specific Bible scripture grounding
    if intent.category == "bible":
        bible_data = retrieved_material.get("bible_data", {})
        if bible_data.get("is_copyrighted"):
            req_trans = bible_data.get("requested_translation", "NIV")
            alt_data = bible_data.get("public_domain_alternative")
            alt_text = f"\nVerified Public Domain Text ({alt_data['translation']}): \"{alt_data['text']}\"" if alt_data else ""
            directives.append(
                f"\nCRITICAL SCRIPTURE TRANSLATION DIRECTIVE:\n"
                f"- The user requested an exact quote in '{req_trans}'.\n"
                f"- '{req_trans}' is a proprietary copyrighted translation not stored in local offline records.\n"
                f"- DO NOT invent or fabricate wording for '{req_trans}'.\n"
                f"- State clearly: \"Exact wording for the {req_trans} translation cannot be verified from available local sources, as it is a proprietary copyrighted translation.\"\n"
                f"- If presenting the verse, clearly provide the public domain translation instead and explicitly identify it.{alt_text}"
            )
        elif bible_data.get("verified") and bible_data.get("text"):
            directives.append(
                f"\nVERIFIED SCRIPTURE PASSAGE ({bible_data.get('reference')} - {bible_data.get('requested_translation')}):\n"
                f"\"{bible_data.get('text')}\"\n"
                f"- Quote this exact text accurately. Do not alter or substitute words."
            )
        else:
            directives.append(
                f"\nSCRIPTURE UNCERTAINTY INSTRUCTION:\n"
                f"- The requested verse text could not be verified from available local sources.\n"
                f"- State clearly: \"I couldn't verify the exact wording from the available sources.\""
            )

    # Specific Document QA Grounding
    elif retrieved_material.get("tier") == 1 and retrieved_material.get("grounding_text"):
        directives.append(
            f"\nDOCUMENT EVIDENCE EXCERPTS:\n"
            f"---\n"
            f"{retrieved_material['grounding_text']}\n"
            f"---\n"
            f"Ground your answer solely in these excerpts. Explicitly cite the document filename and page number."
        )

    # Specific Scientific Facts Grounding
    elif intent.category == "scientific" and retrieved_material.get("grounding_text"):
        directives.append(
            f"\nVERIFIED SCIENTIFIC REFERENCES:\n"
            f"{retrieved_material['grounding_text']}\n"
            f"Express equations in proper LaTeX notation."
        )

    # Specific Historical Grounding
    elif intent.category == "historical" and retrieved_material.get("grounding_text"):
        directives.append(
            f"\nVERIFIED HISTORICAL DATA:\n"
            f"{retrieved_material['grounding_text']}"
        )

    # Specific Academic DOI / Reference Grounding
    elif intent.category == "academic" and retrieved_material.get("is_known_fake_doi"):
        directives.append(
            "\nACADEMIC VERIFICATION DIRECTIVE:\n"
            "The requested identifier could not be validated in trusted academic indexes. "
            "Explicitly warn the user that the DOI could not be verified and avoid inventing paper metadata."
        )

    # General Knowledge / Unverified Fallback
    elif intent.is_factual and not retrieved_material.get("verified"):
        directives.append(
            "\nFACTUAL UNCERTAINTY INSTRUCTION:\n"
            "No independent local reference was found for this factual claim. "
            "Acknowledge that this explanation is based on general model knowledge and has not been independently verified."
        )

    if project_instructions:
        directives.append(f"\nPROJECT INSTRUCTIONS:\n{project_instructions}")

    return "\n\n".join(directives)
