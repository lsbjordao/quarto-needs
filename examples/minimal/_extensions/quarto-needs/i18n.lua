-- Presentation-only localization helpers. Engineering semantics stay in Python.
local M = {}

local function input_file()
  local ok, declared = pcall(function() return quarto.doc.input_file end)
  if ok and type(declared) == "string" and declared ~= "" then return declared end
  local files = PANDOC_STATE and PANDOC_STATE.input_files or nil
  return files and files[1] or ""
end

function M.language()
  local input = input_file()
  local locale = input:match("%.([A-Za-z][A-Za-z0-9%-]*)%.qmd$")
  if locale and locale ~= "" then return locale end
  return "en"
end

function M.is_pt()
  return M.language():lower():match("^pt") ~= nil
end

function M.t(en, pt)
  if M.is_pt() then return pt end
  return en
end

local RELATIONS_PT = {
  ["derives-from"] = {"Deriva de", "Origem de"},
  ["refines"] = {"Refina", "Refinado por"},
  ["decomposes"] = {"Decompõe", "Parte de"},
  ["depends-on"] = {"Depende de", "Dependência de"},
  ["conflicts-with"] = {"Conflita com", "Conflita com"},
  ["constrains"] = {"Restringe", "Restringido por"},
  ["implements"] = {"Implementa", "Implementado por"},
  ["implemented-by"] = {"Implementado por", "Implementa"},
  ["verifies"] = {"Verifica", "Verificado por"},
  ["verified-by"] = {"Verificado por", "Verifica"},
  ["validated-by"] = {"Validado por", "Valida"},
  ["mitigates"] = {"Mitiga", "Mitigado por"},
  ["justified-by"] = {"Justificado por", "Justifica"},
  ["evidences"] = {"Evidencia", "Evidenciado por"},
  ["evidenced-by"] = {"Evidenciado por", "Evidencia"},
  ["references"] = {"Referencia", "Referenciado por"},
  ["addresses"] = {"Endereça", "Endereçado por"},
  ["addressed-by"] = {"Endereçado por", "Endereça"},
  ["applies-to"] = {"Aplica-se a", "Decisão aplicável a"},
  ["supersedes"] = {"Substitui", "Substituído por"},
  ["superseded-by"] = {"Substituído por", "Substitui"},
  ["confirmed-by"] = {"Confirmado por", "Confirma"},
  ["confirms"] = {"Confirma", "Confirmado por"},
}

function M.relation_label(relation_type, inverse, fallback)
  if not M.is_pt() then return fallback end
  local labels = RELATIONS_PT[relation_type]
  if not labels then return fallback end
  return labels[inverse and 2 or 1]
end

return M
