# Accuracy pass

Two independent failure modes. Do both passes.

## 1. Speech recognition garbling

YouTube auto-captions are trained on general speech and fail predictably on medical
vocabulary. Every one of these was observed in a single hematology lecture:

| Transcript says | Actually |
|---|---|
| citroblastic / sideroblast | sideroblastic |
| mincer's index, menser, mensters | Mentzer index |
| micro acidic, normal acidic, macroacidic | microcytic, normocytic, macrocytic |
| basophilic stifling / stipeling | basophilic stippling |
| foley, folie | folate |
| bud chiari | Budd-Chiari |
| vabesiosis | babesiosis |
| a canthocytes | acanthocytes |
| xydovidine | zidovudine |
| phosphoenotoin | fosphenytoin |
| help syndrome | HELLP syndrome |
| sugar toxin | Shiga toxin |
| atom t13 / adam ts13 | ADAMTS13 |
| peroxismal, proximal nocturnal | paroxysmal nocturnal |
| papanheimer bodies | Pappenheimer bodies |
| heinz / hines bodies | Heinz bodies |
| ippo | EPO / erythropoietin |

The general classes to sweep for:

- **Eponyms** are mangled almost every time. Any name-like token is suspect.
- **Acronyms spoken letter by letter** get fused into words.
- **Drug names**, especially anything polysyllabic.
- **Numbers.** "greater than 150 liters" for "greater than 100 femtolitres";
  decimals split across sentence boundaries as the captioner inserts false stops.
- **Units** are frequently dropped entirely. Restore them.
- Words that are near-homophones of a common English word lose to the common word.

Rule: if a term would be wrong in a printed reference, it does not go in the output.
When a garbled token cannot be resolved from context, flag it in your report to the
user rather than guessing at it.

## 2. The lecturer was wrong

Separate from transcription. Lecturers misspeak, simplify past the point of accuracy,
or teach a superseded threshold. Check every clinically load-bearing claim against
current teaching before you repeat it.

Observed examples:

- Sickle cell confirmed by "hemoglobin F on electrophoresis" - it is **hemoglobin S**.
- Ringed sideroblasts described as a peripheral smear finding - they require a
  **marrow aspirate with an iron stain**. The smear shows stippling and Pappenheimer
  bodies.
- Iron studies for chronic disease and thalassemia waved off as "variable" - fine in a
  lecture, a hole in a reference table. Complete them from standard teaching.
- Indices quoted as percentages when they are unitless ratios (the Mentzer index).

What to do:

- **Silently fix** slips that change nothing structurally, e.g. a mis-said unit.
- **Fix and report** anything a reader would act on. List these to the user at the end.
- Where the lecture is deliberately simplified for examinations but the audience is
  clinical, keep the simple rule as scaffolding and add a short section on where it
  breaks down in real patients. Do not silently replace one with the other.

## 3. Epidemiology and language

Lectures often cue conditions off a single demographic ("you see this in young
African-American children"). In a written reference this is both less accurate and
less useful than naming the actual at-risk populations. Write the real distribution.

Use they/them for hypothetical patients unless the vignette fixes a sex for clinical
reasons, e.g. pregnancy, prostate, menstrual history.
