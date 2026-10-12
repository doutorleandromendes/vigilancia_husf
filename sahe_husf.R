# ══════════════════════════════════════════════════════════════════════════════
# SAHE-R v2 · HUSF — UTI A/B · UTI C · UTI Neonatal
# Fonte de dados: data_historico.json + data_iras.json (sem Excel)
#
# Pré-requisito: rodar export_historico.R uma vez para gerar data_historico.json
#
# Uso mensal:
#   source("sahe_uti_ab_husf.R")
# ══════════════════════════════════════════════════════════════════════════════

# ── Pacotes ───────────────────────────────────────────────────────────────────
required <- c("jsonlite","tidyverse","Kendall","trend","boot","exactci","purrr","glue")
to_install <- required[!required %in% rownames(installed.packages())]
if (length(to_install)) install.packages(to_install)
invisible(lapply(required, library, character.only = TRUE))

select <- dplyr::select
filter <- dplyr::filter

# ── Caminhos ──────────────────────────────────────────────────────────────────
REPO_DIR <- "~/vigilancia_husf_braganca"

JSON_IRAS <- file.path(REPO_DIR, "data_iras.json")
JSON_HIST <- file.path(REPO_DIR, "data_historico.json")
JSON_SAHE <- file.path(REPO_DIR, "data_sahe.json")

stopifnot(
  "data_iras.json não encontrado"     = file.exists(JSON_IRAS),
  "data_historico.json não encontrado — rode export_historico.R primeiro" =
    file.exists(JSON_HIST)
)

# ══════════════════════════════════════════════════════════════════════════════
# 1. FUNÇÕES BASE
# ══════════════════════════════════════════════════════════════════════════════

.MESES_PT <- c("jan","fev","mar","abr","mai","jun",
               "jul","ago","set","out","nov","dez")

mes_label <- function(d) {
  paste0(.MESES_PT[lubridate::month(d)], "/", substr(lubridate::year(d), 3, 4))
}

parse_series <- function(arr) {
  if (is.null(arr) || length(arr) == 0) return(NULL)
  MESES_NUM <- setNames(1:12, .MESES_PT)

  row_to_tibble <- function(lbl, val, curr) {
    lbl <- as.character(unlist(lbl))
    if (length(lbl) == 0 || is.na(lbl) || !grepl("/", lbl)) return(NULL)
    parts <- str_split(str_to_lower(lbl), "/")[[1]]
    m  <- MESES_NUM[parts[1]]
    yr <- suppressWarnings(as.integer(paste0("20", parts[2])))
    if (is.na(m) || is.na(yr)) return(NULL)
    val_u  <- unlist(val)
    curr_u <- unlist(curr)
    tibble(
      label    = lbl,
      data_ref = as.Date(sprintf("%d-%02d-01", yr, m)),
      valor    = suppressWarnings(as.numeric(val_u)),
      corrente = length(curr_u) > 0 && isTRUE(as.logical(curr_u))
    )
  }

  if (is.data.frame(arr)) {
    map_dfr(seq_len(nrow(arr)), function(i)
      row_to_tibble(arr$p[i], arr$v[i], arr[["c"]][i]))
  } else {
    map_dfr(arr, function(pt)
      row_to_tibble(pt$p, pt$v, pt[["c"]]))
  }
}

combine_series <- function(hist_arr, iras_arr) {
  s_hist <- parse_series(hist_arr)
  s_iras <- parse_series(iras_arr)
  if (is.null(s_hist) && is.null(s_iras)) return(NULL)
  if (is.null(s_hist)) return(s_iras)
  if (is.null(s_iras)) return(s_hist)
  # JSON prevalece para meses sobrepostos
  s_hist_filt <- s_hist |> filter(!label %in% s_iras$label)
  bind_rows(s_hist_filt, s_iras) |> arrange(data_ref)
}

# ══════════════════════════════════════════════════════════════════════════════
# 2. FUNÇÕES DE ANÁLISE
# ══════════════════════════════════════════════════════════════════════════════

canal_endemico <- function(valores, n_boot = 3000, seed = 42) {
  x <- valores[!is.na(valores)]
  n <- length(x)
  if (n < 8) { warning(sprintf("n=%d < 8 — canal não calculado", n)); return(NULL) }
  set.seed(seed)
  probs <- c(0.10, 0.25, 0.50, 0.75, 0.90)
  b     <- boot(x, function(x,i) quantile(x[i], probs=probs), R=n_boot)
  map_dfr(seq_along(probs), function(k) {
    ci <- tryCatch(boot.ci(b, type="perc", index=k)$percent[4:5], error=\(e) c(NA,NA))
    tibble(quantil=probs[k], estimativa=b$t0[k], ic_inf=ci[1], ic_sup=ci[2])
  })
}

run_mk <- function(valores) {
  x <- valores[!is.na(valores)]
  if (length(x) < 6 || var(x) == 0)
    return(list(tau=NA, p=NA, sen=NA, tendencia="Dados insuficientes"))
  mk  <- MannKendall(x)
  sen <- sens.slope(x)
  tau <- as.numeric(mk$tau[1]); p <- as.numeric(mk$sl[1])
  s   <- as.numeric(sen$estimates)
  tendencia <- case_when(
    p >= 0.05             ~ "Sem tendência significativa",
    tau > 0 & p < 0.001  ~ "↑ Tendência de aumento (p<0,001)",
    tau > 0 & p < 0.01   ~ "↑ Tendência de aumento (p<0,01)",
    tau > 0 & p < 0.05   ~ "↑ Tendência de aumento (p<0,05)",
    tau < 0 & p < 0.001  ~ "↓ Tendência de redução (p<0,001)",
    tau < 0 & p < 0.01   ~ "↓ Tendência de redução (p<0,01)",
    tau < 0 & p < 0.05   ~ "↓ Tendência de redução (p<0,05)",
    TRUE                  ~ "Indeterminado"
  )
  list(tau=tau, p=p, sen=s, tendencia=tendencia)
}

avaliar_mes <- function(valor, historico, canal_q) {
  if (is.na(valor) || is.null(canal_q)) return(NULL)
  hist <- historico[!is.na(historico)]
  if (length(hist) < 4) return(NULL)
  mu       <- mean(hist)
  pct_rank <- mean(hist <= valor) * 100
  q        <- setNames(canal_q$estimativa, as.character(canal_q$quantil))
  zona <- case_when(
    valor < q["0.1"]  ~ "Abaixo do esperado",
    valor < q["0.25"] ~ "Zona baixa (favorável)",
    valor < q["0.75"] ~ "Zona endêmica",
    valor < q["0.9"]  ~ "Zona de alerta",
    TRUE              ~ "Zona epidêmica"
  )
  p_poisson <- poisson.test(max(1L, round(valor)), r=mu, alternative="greater")$p.value
  list(pct_rank=pct_rank, zona=zona, p_poisson=p_poisson)
}

sahe_unit <- function(serie, label_unit="", ref_filter=NULL) {
  if (is.null(serie) || nrow(serie) < 8) {
    cat(sprintf("  ⚠ %-30s: %d pts (mínimo 8)\n",
                label_unit, if(is.null(serie)) 0L else nrow(serie)))
    return(NULL)
  }
  ref <- (if (!is.null(ref_filter)) ref_filter(serie) else serie) |>
    filter(!corrente)
  if (nrow(ref) < 8) {
    cat(sprintf("  ⚠ %-30s: %d pts referência após filtro\n", label_unit, nrow(ref)))
    return(NULL)
  }
  canal <- canal_endemico(ref$valor)
  if (is.null(canal)) return(NULL)
  mk <- run_mk(serie$valor)

  meses_list <- list()
  for (i in seq_len(nrow(serie))) {
    row <- serie[i,]
    if (is.na(row$valor)) next
    aval <- avaliar_mes(row$valor, ref$valor, canal)
    if (is.null(aval)) next
    zona_code <- case_when(
      str_detect(aval$zona, "epidêmica") ~ "epidemica",
      str_detect(aval$zona, "alerta")   ~ "alerta",
      str_detect(aval$zona, "Abaixo")   ~ "abaixo",
      str_detect(aval$zona, "baixa")    ~ "baixa",
      TRUE                              ~ "endemica"
    )
    meses_list[[row$label]] <- list(
      zona  = zona_code,
      pct   = round(aval$pct_rank),
      p_poi = round(aval$p_poisson, 4)
    )
  }

  cat(sprintf("  ✓ %-30s: total=%d ref=%d meses=%d | %s\n",
              label_unit, nrow(serie), nrow(ref), length(meses_list), mk$tendencia))
  list(
    p10=round(canal$estimativa[canal$quantil==0.10],2),
    p25=round(canal$estimativa[canal$quantil==0.25],2),
    p50=round(canal$estimativa[canal$quantil==0.50],2),
    p75=round(canal$estimativa[canal$quantil==0.75],2),
    p90=round(canal$estimativa[canal$quantil==0.90],2),
    mk_tau=if(is.na(mk$tau)) NA else round(mk$tau,3),
    mk_p  =if(is.na(mk$p))  NA else round(mk$p, 4),
    mk_dir=if(is.na(mk$tau)) 0L else sign(mk$tau),
    sen   =if(is.na(mk$sen)) NA else round(mk$sen,3),
    meses =meses_list
  )
}

# ══════════════════════════════════════════════════════════════════════════════
# 3. LEITURA
# ══════════════════════════════════════════════════════════════════════════════

cat("\n=== Lendo data_historico.json ===\n")
hist_raw <- read_json(JSON_HIST)
cat(sprintf("  Período: %s a %s\n", hist_raw$periodo$inicio, hist_raw$periodo$fim))

cat("=== Lendo data_iras.json ===\n")
iras_raw <- read_json(JSON_IRAS, simplifyDataFrame=FALSE)
cat(sprintf("  Período corrente: %s\n", iras_raw$periodo))

pos_covid_filter <- function(s) filter(s, data_ref >= as.Date("2022-01-01"))

# ══════════════════════════════════════════════════════════════════════════════
# 4. ANÁLISE
# ══════════════════════════════════════════════════════════════════════════════

sahe_out <- list(gerado=format(Sys.Date(),"%Y-%m-%d"))

# ── UTI A/B ───────────────────────────────────────────────────────────────────
cat("\n=== UTI A/B (ref: pós-COVID jan/2022+) ===\n")
utiAB_r <- list()
for (k in c("pav","ipcs","cvc","svd")) {
  s <- combine_series(hist_raw$utiAB[[k]], iras_raw$utiAB[[k]])
  utiAB_r[[k]] <- sahe_unit(s, glue("UTI A/B · {toupper(k)}"), pos_covid_filter)
}
# Meta de referência
s_ref <- combine_series(hist_raw$utiAB$pav, iras_raw$utiAB$pav)
ref_ab <- if(!is.null(s_ref)) pos_covid_filter(s_ref)|>filter(!corrente) else tibble(data_ref=as.Date(character()))
sahe_out$utiAB <- c(
  list(ref_inicio=if(nrow(ref_ab)>0) mes_label(min(ref_ab$data_ref)) else NA,
       ref_fim   =if(nrow(ref_ab)>0) mes_label(max(ref_ab$data_ref)) else NA,
       n_ref     =nrow(ref_ab)),
  utiAB_r)

# ── UTI C ─────────────────────────────────────────────────────────────────────
cat("\n=== UTI C (ref: série completa) ===\n")
utic_r <- list()
for (k in c("pav","ipcs","cvc","svd")) {
  s <- combine_series(hist_raw$utic[[k]], iras_raw$utic[[k]])
  utic_r[[k]] <- sahe_unit(s, glue("UTI C · {toupper(k)}"))
}
s_ref_c  <- combine_series(hist_raw$utic$pav, iras_raw$utic$pav)
ref_c    <- if(!is.null(s_ref_c)) filter(s_ref_c,!corrente) else tibble(data_ref=as.Date(character()))
sahe_out$utic <- c(
  list(ref_inicio=if(nrow(ref_c)>0) mes_label(min(ref_c$data_ref)) else NA,
       ref_fim   =if(nrow(ref_c)>0) mes_label(max(ref_c$data_ref)) else NA,
       n_ref     =nrow(ref_c)),
  utic_r)

# ── UTI Neonatal ───────────────────────────────────────────────────────────────
cat("\n=== UTI Neo (ref: série completa) ===\n")
neo_s   <- combine_series(hist_raw$utiNeo$ipcs, iras_raw$utiNeo$ipcs)
ref_neo <- if(!is.null(neo_s)) filter(neo_s,!corrente) else tibble(data_ref=as.Date(character()))
sahe_out$utiNeo <- list(
  ref_inicio=if(nrow(ref_neo)>0) mes_label(min(ref_neo$data_ref)) else NA,
  ref_fim   =if(nrow(ref_neo)>0) mes_label(max(ref_neo$data_ref)) else NA,
  n_ref     =nrow(ref_neo),
  ipcs      =sahe_unit(neo_s, "UTI Neo · IPCS")
)
# ── Hemodiálise ────────────────────────────────────────────────────────────────
cat("\n=== Hemodiálise (ref: série completa) ===\n")

# HD não tem data_historico separado — usa apenas data_iras.json
# Indicadores: ilav/bact combinados + por tipo de cateter
hd_r <- list()
for (k in c("ilav","bact","ilavTemp","ilavPerm","bactTemp","bactPerm")) {
  s <- parse_series(iras_raw$hd[[k]])
  if (is.null(s) || nrow(s) < 8) {
    cat(sprintf("  ⚠ HD · %-12s: %d pts — insuficiente\n",
                toupper(k), if(is.null(s)) 0L else nrow(s)))
    next
  }
  hd_r[[k]] <- sahe_unit(s, glue("HD · {toupper(k)}"))
}

# Período de referência (série mais longa com dados suficientes)
ref_hd_key <- names(hd_r)[1]
ref_hd_s   <- parse_series(iras_raw$hd[[ref_hd_key]])
ref_hd     <- if (!is.null(ref_hd_s)) filter(ref_hd_s, !corrente) else
  tibble(data_ref = as.Date(character()))

sahe_out$hd <- c(
  list(
    ref_inicio = if (nrow(ref_hd) > 0) mes_label(min(ref_hd$data_ref)) else NA,
    ref_fim    = if (nrow(ref_hd) > 0) mes_label(max(ref_hd$data_ref)) else NA,
    n_ref      = nrow(ref_hd)
  ),
  hd_r
)
# ══════════════════════════════════════════════════════════════════════════════
# 5. ESCREVER data_sahe.json
# ══════════════════════════════════════════════════════════════════════════════

write_json(sahe_out, JSON_SAHE, auto_unbox=TRUE, pretty=TRUE, null="null")
cat(glue("\n✓ {JSON_SAHE}\n"))
cat("  git add data_sahe.json && git commit -m 'sahe: atualiza canal' && git push\n\n")

cat("=== RESUMO ===\n")
for (unit in c("utiAB","utic","utiNeo","hd")) {
  u <- sahe_out[[unit]]
  cat(sprintf("\n%s  ref: %s–%s (n=%d)\n",
              unit, u$ref_inicio%||%"?", u$ref_fim%||%"?", u$n_ref%||%0L))
  for (k in intersect(c("pav","ipcs","cvc","svd","ilav","bact","ilavTemp","ilavPerm","bactTemp","bactPerm"), names(u))) {
    r <- u[[k]]
    if (!is.null(r))
      cat(sprintf("  %-4s P50=%-5.1f P90=%-5.1f  τ=%-6.3f p=%.3f\n",
                  k, r$p50, r$p90, r$mk_tau%||%NA_real_, r$mk_p%||%NA_real_))
  }
}
