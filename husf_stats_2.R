# =============================================================================
# husf_stats.R  v4.0  Mai 2026
# Analise estatistica - DOT de ATBs e MDR - HUSF / SCIH-CCIH
# Dr. Leandro Mendes - Braganca Paulista
# =============================================================================
# Arquivos no diretorio de trabalho:
#   - data_iras.json          (obrigatorio)
#   - data_mensal_hist.json   (opcional, gerado por backfill_historico.py)
# Saida: console + husf_stats_output.json
# =============================================================================

suppressPackageStartupMessages(library(jsonlite))

cat(rep("=",70),"\n",sep="")
cat("HUSF - SCIH-CCIH - Analise Estatistica - ATB DOTs e MDR\n")
cat(format(Sys.time(),"%d/%m/%Y %H:%M"),"\n")
cat(rep("=",70),"\n\n",sep="")

# =============================================================================
# 0. CARREGAR DADOS
# =============================================================================
json_path <- '/Users/leandromendes/vigilancia_husf_braganca/data_iras.json'
if (!file.exists(json_path)) stop("data_iras.json nao encontrado no diretorio de trabalho.")
D <- fromJSON(json_path, simplifyVector = FALSE)
cat("OK data_iras.json carregado - periodo:", D$periodo, "\n")

# Carrega historico mensal backfill (se disponivel)
hist_path <- '/Users/leandromendes/vigilancia_husf_braganca/data_mensal_hist.json'
HIST <- NULL

if(!file.exists("data_iras.json")) stop("data_iras.json nao encontrado.")
D    <- fromJSON("data_iras.json", simplifyVector=FALSE)
HIST <- NULL
if(file.exists("data_mensal_hist.json")) {
  HIST <- fromJSON("data_mensal_hist.json", simplifyVector=FALSE)
  cat("OK data_iras.json +  data_mensal_hist.json\n")
  cat("   periodo iras:", D$periodo, " | hist gerado:", HIST$gerado,"\n\n")
} else {
  cat("OK data_iras.json carregado. (sem data_mensal_hist.json)\n\n")
}

# =============================================================================
# METADADOS DE ATBs E UNIDADES
# =============================================================================
# Nomes canonicos inferidos das chaves JSON — adicionar aqui se novos ATBs
# forem incorporados ao pipeline no futuro.

ATB_NOMES <- c(cef="Ceftriaxona", pip="Pip/Tazo", cbp="Carbapenemico",
               gpp="Glicopeptideo", pb="Polimixina B")

UNIT_NOMES <- c(utiab="UTI A/B", utic="UTI C", clin="Cl.Medica",
                cir="Cl.Cirurgica", apto="Apartamentos", epm="EPM")

# Prioridade clinica: define ordem de exibicao e pesos para CCF
# (nao afeta o calculo — apenas a apresentacao)
ATB_ORDEM  <- c("cef","pip","cbp","gpp","pb")
UNIT_ORDEM <- c("utiab","utic","clin","cir","apto","epm")

MESES_PT <- c("jan","fev","mar","abr","mai","jun","jul","ago","set","out","nov","dez")

`%||%` <- function(a,b) if(!is.null(a) && !is.na(a) && nchar(as.character(a))>0) a else b

# =============================================================================
# FUNCOES AUXILIARES
# =============================================================================

sort_mes <- function(lbl) {
  parts <- strsplit(lbl,"/")[[1]]
  as.integer(parts[2])*100 + match(parts[1], MESES_PT)
}

get_annual_pv <- function(lst) {
  df <- do.call(rbind, lapply(lst, function(x)
    data.frame(p=x$p, v=as.numeric(x$v), stringsAsFactors=FALSE)))
  df <- df[grepl("^[0-9]{4}$", df$p),]
  df$year <- as.integer(df$p)
  df[order(df$year),]
}

get_annual_mdr <- function(lst) {
  df <- do.call(rbind, lapply(lst, function(x)
    data.frame(p=x$p, e=as.numeric(x$e), k=as.numeric(x$k),
               a=as.numeric(x$a), stringsAsFactors=FALSE)))
  df <- df[grepl("^[0-9]{4}$", df$p),]
  df$year <- as.integer(df$p)
  df[order(df$year),]
}

# Merge DOT mensal: HIST (2025) + D$dots (2026), com prioridade para 2026
merge_dot <- function(atb, unit) {
  pts <- list()
  if(!is.null(HIST$dots[[atb]][[unit]]))
    for(pt in HIST$dots[[atb]][[unit]])
      pts[[pt$p]] <- as.numeric(pt$v)
  if(!is.null(D$dots[[atb]][[unit]]))
    for(pt in D$dots[[atb]][[unit]])
      pts[[pt$p]] <- as.numeric(pt$v)
  if(length(pts)==0) return(data.frame(p=character(),v=numeric()))
  lbls <- names(pts)
  lbls <- lbls[order(sapply(lbls, sort_mes))]
  data.frame(p=lbls, v=unname(unlist(pts[lbls])), stringsAsFactors=FALSE)
}

# Merge MDR mensal
merge_mdr <- function(unit, org) {
  pts <- list()
  if(!is.null(HIST$mdrMensal[[unit]][[org]]))
    for(pt in HIST$mdrMensal[[unit]][[org]])
      pts[[pt$p]] <- list(v=as.numeric(pt$v),
                          pd=as.integer(if(!is.null(pt$pd)) pt$pd else 0))
  src <- if(unit=="utiAB") "utiAB" else unit
  if(!is.null(D$mdrMensal[[src]][[org]]))
    for(pt in D$mdrMensal[[src]][[org]])
      pts[[pt$p]] <- list(v=as.numeric(pt$v),
                          pd=as.integer(if(!is.null(pt$pd)) pt$pd else 0))
  if(length(pts)==0) return(data.frame(p=character(),v=numeric(),pd=integer()))
  lbls <- names(pts); lbls <- lbls[order(sapply(lbls,sort_mes))]
  data.frame(p=lbls, v=sapply(lbls,function(l)pts[[l]]$v),
             pd=sapply(lbls,function(l)pts[[l]]$pd), stringsAsFactors=FALSE)
}

# Descobre ATBs e unidades disponiveis dinamicamente no JSON
get_atbs_disponiveis <- function() {
  atbs_hist <- if(!is.null(HIST)) names(HIST$dots) else character(0)
  atbs_iras <- if(!is.null(D$dots)) names(D$dots) else character(0)
  atbs <- unique(c(atbs_hist, atbs_iras))
  atbs_ord <- ATB_ORDEM[ATB_ORDEM %in% atbs]
  c(atbs_ord, setdiff(atbs, ATB_ORDEM))  # ordena por prioridade, depois resto
}

get_units_disponiveis <- function(atb) {
  units_hist <- if(!is.null(HIST$dots[[atb]])) names(HIST$dots[[atb]]) else character(0)
  units_iras <- if(!is.null(D$dots[[atb]])) names(D$dots[[atb]]) else character(0)
  units <- unique(c(units_hist, units_iras))
  units_ord <- UNIT_ORDEM[UNIT_ORDEM %in% units]
  c(units_ord, setdiff(units, UNIT_ORDEM))
}

# Mann-Kendall base R
mann_kendall <- function(x) {
  x <- x[!is.na(x)]
  n <- length(x); if(n < 4) return(list(tau=NA,Z=NA,p.value=NA))
  S <- 0
  for(i in seq_len(n-1)) for(j in (i+1):n) S <- S+sign(x[j]-x[i])
  varS <- n*(n-1)*(2*n+5)/18
  Z  <- ifelse(S>0,(S-1),ifelse(S<0,(S+1),0))/sqrt(varS)
  list(S=S, tau=S/(n*(n-1)/2), Z=Z, p.value=2*(1-pnorm(abs(Z))))
}

# Joinpoint por busca exaustiva (eixo numerico 1..n)
joinpoint_fit <- function(t, y, min_seg=3) {
  ok <- !is.na(y)
  t <- t[ok]; y <- y[ok]; n <- length(t)
  if(n < 2*min_seg) return(list(jp=NA,jp_lbl=NA,ci_l_lbl=NA,ci_u_lbl=NA,
                                 sb=NA,sa=NA,p=NA))
  fit0 <- lm(y~t); rss0 <- sum(resid(fit0)^2)
  cands <- t[min_seg:(n-min_seg+1)]
  if(length(cands)==0) return(list(jp=NA,jp_lbl=NA,ci_l_lbl=NA,ci_u_lbl=NA,
                                    sb=NA,sa=NA,p=1))
  rss_v <- sapply(cands, function(bp){
    x1 <- pmax(0,t-bp)
    fit1 <- tryCatch(lm(y~t+x1),error=function(e)NULL)
    if(is.null(fit1)) Inf else sum(resid(fit1)^2)})
  bp  <- cands[which.min(rss_v)]; rss1 <- min(rss_v)
  df1 <- 1; df2 <- n-4
  if(df2 < 1) return(list(jp=NA,jp_lbl=NA,ci_l_lbl=NA,ci_u_lbl=NA,sb=NA,sa=NA,p=1))
  pval <- pf(((rss0-rss1)/df1)/(rss1/df2),df1,df2,lower.tail=FALSE)
  if(pval >= 0.10) return(list(jp=NA,jp_lbl=NA,ci_l_lbl=NA,ci_u_lbl=NA,
                                sb=NA,sa=NA,p=pval))
  x1 <- pmax(0,t-bp); fit1 <- lm(y~t+x1); co <- coef(fit1)
  set.seed(42)
  bp_b <- replicate(500,{
    idx <- sample(n,replace=TRUE); yb <- y[idx]; tb <- t[idx]
    rv  <- sapply(cands,function(b){
      x1b <- pmax(0,tb-b)
      fb  <- tryCatch(lm(yb~tb+x1b),error=function(e)NULL)
      if(is.null(fb)) Inf else sum(resid(fb)^2)})
    cands[which.min(rv)]})
  list(jp=bp, jp_lbl=bp,
       ci_l_lbl=quantile(bp_b,0.05,na.rm=TRUE),
       ci_u_lbl=quantile(bp_b,0.95,na.rm=TRUE),
       sb=co["t"], sa=co["t"]+co["x1"], p=pval)
}

# Converte indice de breakpoint para label de mes (dado vetor de labels)
idx_to_lbl <- function(idx, labels) {
  i <- max(1, min(round(idx), length(labels)))
  labels[i]
}

# CUSUM de Page one-sided upper
cusum_page <- function(obs, mu0, s0, k_mult=0.5, h_mult=4.0) {
  if(is.na(s0)||s0<=0) s0 <- max(mu0*0.20, 1)
  k <- k_mult*s0; h <- h_mult*s0
  S <- numeric(length(obs)+1)
  for(t in seq_along(obs)) S[t+1] <- max(0, S[t]+(obs[t]-mu0-k))
  list(S=S[-1], h=h, alarme=any(S[-1]>=h), mu0=mu0, s0=s0)
}

# Shannon H'
shannon_h <- function(v) {
  v <- v[!is.na(v)&v>0]
  if(!length(v)) return(NA_real_)
  p <- v/sum(v); -sum(p*log(p))
}

sec <- function(t) {
  cat("\n",rep("-",70),"\n",sep="")
  cat(" ",t,"\n")
  cat(rep("-",70),"\n",sep="")
}

# =============================================================================
# DIAGNOSTICO DE SERIES
# =============================================================================

ATBS <- get_atbs_disponiveis()

cat("-- Series mensais disponiveis --\n")
n_meses_dot <- 0
for(atb in ATBS) {
  units <- get_units_disponiveis(atb)
  nome  <- ATB_NOMES[atb] %||% atb
  for(unit in units) {
    df <- merge_dot(atb, unit)
    if(nrow(df)==0) next
    n_nz <- sum(df$v > 0)
    if(unit == "utiab" && atb == "cbp") n_meses_dot <- nrow(df)
    cat(sprintf("  DOT %-16s %-14s  %2d meses (%d nao-zero)  %s->%s\n",
                ATB_NOMES[atb]%||%atb, UNIT_NOMES[unit]%||%unit,
                nrow(df), n_nz, df$p[1], df$p[nrow(df)]))
  }
}

# MDR
mdr_ab_kpc  <- merge_mdr("utiAB","kpc")
mdr_ab_esbl <- merge_mdr("utiAB","esbl")
mdr_ab_acin <- merge_mdr("utiAB","acin")
mdr_uc_kpc  <- merge_mdr("utic","kpc")
mdr_uc_esbl <- merge_mdr("utic","esbl")
mdr_uc_acin <- merge_mdr("utic","acin")

n_mdr <- nrow(mdr_ab_kpc)
ccf_ok       <- (n_meses_dot >= 15 && n_mdr >= 15)
cusum_ok     <- (n_mdr >= 12)

cat(sprintf("\n  MDR KPC UTI A/B            %2d meses\n", n_mdr))
cat(sprintf("  CCF DOT->MDR   : %s (%d/%d)\n",
            if(ccf_ok)"ATIVO" else "aguardando", min(n_meses_dot,n_mdr), 15))
cat(sprintf("  CUSUM mensal   : %s\n\n",
            if(cusum_ok)"ATIVO (Phase 1 mensal)" else "fallback anual"))

# =============================================================================
# MODULO 1 - TENDENCIA DOT ANUAL UTI A/B (referencia historica 2020-2025)
# =============================================================================

sec("MODULO 1 - TENDENCIA DOT ANUAL UTI A/B (2020-2025, referencia historica)")
cat("  Nota: serie anual — arco de longo prazo, 6 pts, poder limitado.\n\n")

DOT_ANUAL <- list(
  list(k="dddPip",  lb="Pip/Tazo"),  list(k="dddCarba",lb="Carbapenemico"),
  list(k="dddGlico",lb="Glicopeptideo"), list(k="dddPoli",lb="Polimixina B"))

mk1 <- list(); jp1 <- list()
for(m in DOT_ANUAL) {
  df  <- get_annual_pv(D$utiAB[[m$k]])
  if(nrow(df)<4){cat(sprintf("  %-16s  insuficiente\n",m$lb));next}
  mk  <- mann_kendall(df$v)
  jp  <- joinpoint_fit(df$year, df$v)
  sig <- if(!is.na(mk$p.value)&&mk$p.value<0.05)"*" else if(!is.na(mk$p.value)&&mk$p.value<0.10)"+" else " "
  dir <- if(!is.na(mk$tau)&&mk$tau>0)"up" else "dn"
  cat(sprintf("  %-16s  tau=%6.3f  Z=%5.2f  p=%.4f  %s%s",
              m$lb, mk$tau%||%NA, mk$Z%||%NA, mk$p.value%||%NA, dir, sig))
  if(!is.na(jp$jp))
    cat(sprintf("  | JP=%d (%.1f->%.1f/ano)",round(jp$jp),jp$sb,jp$sa))
  cat("\n")
  mk1[[m$k]] <- mk; jp1[[m$k]] <- jp
}

# =============================================================================
# MODULO 1b - TENDENCIA DOT MENSAL — TODAS ATBs x TODAS UNIDADES
# =============================================================================

sec("MODULO 1b - TENDENCIA DOT MENSAL — todas ATBs x todas unidades")
cat("  Criterio de inclusao: >= 8 meses com valor > 0\n")
cat("  (series com muitos zeros — ex: polimixina em enfermarias — sao sinalizadas)\n\n")

cat(sprintf("  %-18s %-14s %3s  %7s %5s %6s  %s\n",
            "ATB","Unidade","n","tau","p","Z","Tendencia / Joinpoint"))
cat("  ",paste(rep("-",80),collapse=""),"\n")

mk1b <- list(); jp1b <- list()
RESULTADOS_DOT <- list()  # para exportacao e CCF

for(atb in ATBS) {
  units <- get_units_disponiveis(atb)
  for(unit in units) {
    df   <- merge_dot(atb, unit)
    if(nrow(df)==0) next

    n_nz <- sum(df$v > 0, na.rm=TRUE)
    flag_zeros <- if(n_nz < nrow(df)*0.5) " [!muitos zeros]" else ""

    if(n_nz < 8) {
      cat(sprintf("  %-18s %-14s %3d  -- insuficiente (%d nao-zero)%s\n",
                  ATB_NOMES[atb]%||%atb, UNIT_NOMES[unit]%||%unit,
                  nrow(df), n_nz, flag_zeros))
      next
    }

    t_idx <- seq_len(nrow(df))
    mk  <- mann_kendall(df$v)
    jp  <- joinpoint_fit(t_idx, df$v)

    sig <- if(!is.na(mk$p.value)&&mk$p.value<0.05)"*" else
           if(!is.na(mk$p.value)&&mk$p.value<0.10)"+" else " "
    dir <- if(!is.na(mk$tau)&&mk$tau>0)"crescente" else "decrescente"

    jp_str <- if(!is.na(jp$jp))
      sprintf("JP=%s->%s (%.2f->%.2f/mes p=%.3f)",
              idx_to_lbl(jp$ci_l_lbl,df$p),
              idx_to_lbl(jp$ci_u_lbl,df$p),
              jp$sb, jp$sa, jp$p)
    else sprintf("sem quebra (p=%.3f)", jp$p%||%1)

    cat(sprintf("  %-18s %-14s %3d  %6.3f %5.3f %5.2f  %s%s  %s%s\n",
                ATB_NOMES[atb]%||%atb, UNIT_NOMES[unit]%||%unit,
                nrow(df), mk$tau, mk$p.value, mk$Z,
                dir, sig, jp_str, flag_zeros))

    key <- paste0(atb,"_",unit)
    mk1b[[key]] <- mk; jp1b[[key]] <- jp
    RESULTADOS_DOT[[key]] <- df
  }
}
cat("\n  * p<0.05  + p<0.10\n")

# =============================================================================
# MODULO 1c - DOT INSTITUCIONAL TOTAL (soma das unidades por ATB)
# =============================================================================
# Perspectiva de stewardship: consumo agregado do hospital inteiro.
# Soma simples das unidades disponiveis em cada mes — interpolar meses
# ausentes em alguma unidade seria enviesado, por isso soma so meses
# em que TODAS as unidades tem dado (inner join por label).
# =============================================================================

sec("MODULO 1c - DOT INSTITUCIONAL TOTAL por ATB (soma das unidades)")
cat("  Soma das unidades com dado disponivel no mes.\n")
cat("  Mais relevante para stewardship do que por unidade isolada.\n\n")

cat(sprintf("  %-18s %3s  %7s %5s  %s\n","ATB","n","tau","p","Tendencia / Joinpoint"))
cat("  ",paste(rep("-",65),collapse=""),"\n")

mk1c <- list()
for(atb in ATBS) {
  units <- get_units_disponiveis(atb)
  # Coleta todas as series
  series_list <- lapply(units, function(u) merge_dot(atb, u))
  series_list <- series_list[sapply(series_list, nrow) > 0]
  if(length(series_list)==0) next

  # Meses comuns a todas as unidades
  all_meses <- Reduce(intersect, lapply(series_list, `[[`, "p"))
  if(length(all_meses) < 8) {
    cat(sprintf("  %-18s  meses comuns insuficientes (%d)\n",
                ATB_NOMES[atb]%||%atb, length(all_meses))); next
  }

  # Soma por mes
  all_meses_ord <- all_meses[order(sapply(all_meses,sort_mes))]
  soma <- sapply(all_meses_ord, function(m) {
    sum(sapply(series_list, function(df) {
      v <- df$v[df$p==m]; if(length(v)) v[1] else 0
    }))
  })
  df_inst <- data.frame(p=all_meses_ord, v=soma, stringsAsFactors=FALSE)

  t_idx <- seq_len(nrow(df_inst))
  mk  <- mann_kendall(df_inst$v)
  jp  <- joinpoint_fit(t_idx, df_inst$v)

  sig <- if(!is.na(mk$p.value)&&mk$p.value<0.05)"*" else
         if(!is.na(mk$p.value)&&mk$p.value<0.10)"+" else " "
  dir <- if(!is.na(mk$tau)&&mk$tau>0)"crescente" else "decrescente"

  jp_str <- if(!is.na(jp$jp))
    sprintf("JP=%s->%s (%.1f->%.1f/mes)",
            idx_to_lbl(jp$ci_l_lbl,df_inst$p),
            idx_to_lbl(jp$ci_u_lbl,df_inst$p),
            jp$sb, jp$sa)
  else "sem quebra"

  cat(sprintf("  %-18s %3d  %6.3f %5.3f  %s%s  %s\n",
              ATB_NOMES[atb]%||%atb, nrow(df_inst),
              mk$tau, mk$p.value, dir, sig, jp_str))

  # Resumo de consumo: media, tendencia mensal e projecao anual
  media_mensal <- mean(df_inst$v)
  proj_anual   <- media_mensal * 12
  cat(sprintf("    media mensal: %.1f DOT/1000pd-total  |  proj. anual: %.0f\n",
              media_mensal, proj_anual))

  mk1c[[atb]] <- list(mk=mk, jp=jp, df=df_inst)
}
cat("\n  * p<0.05  + p<0.10\n")

# =============================================================================
# MODULO 2 - TENDENCIA MDR ANUAL
# =============================================================================

sec("MODULO 2 - TENDENCIA MDR ANUAL (Mann-Kendall + Joinpoint)")

MDR_UNITS <- list(
  list(k="utiAB",lb="UTI A/B",  g=function()D$utiAB$mdr),
  list(k="utic", lb="UTI C",    g=function()D$utic$mdr),
  list(k="inst",  lb="Institucional", g=function()D$mdrInst$s))
ORG_LB <- c(e="ESBL",k="KPC",a="Acinetobacter")
mk2 <- list()

for(u in MDR_UNITS) {
  df <- get_annual_mdr(u$g())
  cat(sprintf("\n  -- %s (%d anos: %d-%d) --\n",
              u$lb,nrow(df),min(df$year),max(df$year)))
  mk2[[u$k]] <- list()
  for(org in names(ORG_LB)) {
    vals <- df[[org]]
    if(all(is.na(vals))||length(vals)<4){cat(sprintf("    %-14s  insuficiente\n",ORG_LB[org]));next}
    mk  <- mann_kendall(vals); jp <- joinpoint_fit(df$year,vals)
    sig <- if(!is.na(mk$p.value)&&mk$p.value<0.05)"*" else
           if(!is.na(mk$p.value)&&mk$p.value<0.10)"+" else " "
    cat(sprintf("    %-14s  tau=%6.3f  p=%.4f  %s%s",
                ORG_LB[org],mk$tau,mk$p.value,
                if(!is.na(mk$tau)&&mk$tau>0)"up" else "dn",sig))
    if(!is.na(jp$jp)) cat(sprintf("  | JP=%d (%.1f->%.1f/ano)",round(jp$jp),jp$sb,jp$sa))
    cat("\n")
    mk2[[u$k]][[org]] <- list(mk=mk,jp=jp)
  }
}
cat("\n  * p<0.05  + p<0.10\n")

# =============================================================================
# MODULO 2b - TENDENCIA MDR MENSAL
# =============================================================================

sec("MODULO 2b - TENDENCIA MDR MENSAL (fev/25 em diante)")

MDR_MENSAL <- list(
  list(u="utiAB",o="kpc", lb="KPC UTI A/B",   df=mdr_ab_kpc),
  list(u="utiAB",o="esbl",lb="ESBL UTI A/B",  df=mdr_ab_esbl),
  list(u="utiAB",o="acin",lb="Acin. UTI A/B", df=mdr_ab_acin),
  list(u="utic", o="kpc", lb="KPC UTI C",     df=mdr_uc_kpc),
  list(u="utic", o="esbl",lb="ESBL UTI C",    df=mdr_uc_esbl),
  list(u="utic", o="acin",lb="Acin. UTI C",   df=mdr_uc_acin))

mk2b <- list()
cat(sprintf("  %-18s %3s  %7s %5s %5s  %s\n","Organismo/Unidade","n","tau","p","Z","Tendencia / Joinpoint"))
cat("  ",paste(rep("-",75),collapse=""),"\n")

for(m in MDR_MENSAL) {
  df <- m$df
  if(nrow(df)<6){cat(sprintf("  %-18s  insuficiente\n",m$lb));next}
  t_idx <- seq_len(nrow(df))
  mk  <- mann_kendall(df$v); jp <- joinpoint_fit(t_idx,df$v)
  sig <- if(!is.na(mk$p.value)&&mk$p.value<0.05)"*" else
         if(!is.na(mk$p.value)&&mk$p.value<0.10)"+" else " "
  dir <- if(!is.na(mk$tau)&&mk$tau>0)"crescente" else "decrescente"
  jp_str <- if(!is.na(jp$jp))
    sprintf("JP=%s->%s (%.2f->%.2f p=%.3f)",
            idx_to_lbl(jp$ci_l_lbl,df$p),idx_to_lbl(jp$ci_u_lbl,df$p),
            jp$sb,jp$sa,jp$p)
  else sprintf("sem quebra (p=%.3f)",jp$p%||%1)
  cat(sprintf("  %-18s %3d  %6.3f %5.3f %5.2f  %s%s  %s\n",
              m$lb,nrow(df),mk$tau,mk$p.value,mk$Z,dir,sig,jp_str))
  mk2b[[paste0(m$u,"_",m$o)]] <- list(mk=mk,jp=jp)
}
cat("\n  * p<0.05  + p<0.10\n")

# =============================================================================
# MODULO 3 - CUSUM DE PAGE (MDR)
# =============================================================================

sec("MODULO 3 - CUSUM DE PAGE - MDR")
if(cusum_ok) { cat("  Phase 1 = primeiros 12 meses mensais | Phase 2 = restantes\n\n") } else { cat("  Phase 1 = media/DP anuais (fallback)\n\n") }
cat("  k=0.5*sigma  h=4*sigma\n\n")

cusum_res <- list()

cusum_unit <- function(u_key, u_lb, mdr_list) {
  cat(sprintf("  -- %s --\n",u_lb))
  cat(sprintf("  %-16s  %10s   Smax    h      Status\n","Organismo","mu0+/-s0"))
  r <- list()
  for(m in mdr_list) {
    df <- m$df
    if(cusum_ok && nrow(df)>=12) {
      p1 <- df$v[1:12]; p2 <- df$v[13:nrow(df)]
      mu0 <- mean(p1,na.rm=TRUE); s0 <- sd(p1,na.rm=TRUE)
    } else {
      df_ann <- get_annual_mdr(if(u_key=="utiAB") D$utiAB$mdr else D$utic$mdr)
      base <- df_ann[[m$org]]
      mu0 <- mean(base,na.rm=TRUE); s0 <- sd(base,na.rm=TRUE)
      df_m <- tryCatch(
        {src <- if(u_key=="utiAB") D$utiAB$mdr else D$utic$mdr
         dm <- do.call(rbind,lapply(src,function(x)
           data.frame(p=x$p,v=as.numeric(x[[m$org]]),stringsAsFactors=FALSE)))
         dm[grepl("/",dm$p),]},
        error=function(e) data.frame(p=character(),v=numeric()))
      p2 <- if(nrow(df_m)>0) df_m$v else numeric(0)
    }
    if(!length(p2)){cat(sprintf("  %-16s  sem phase 2\n",m$lb));next}
    cs <- cusum_page(p2,mu0,s0)
    sta <- if(cs$alarme)"ALARME **" else "Controle"
    cat(sprintf("  %-16s  %5.1f+/-%4.1f   %5.2f  %5.2f  %s\n",
                m$lb,mu0,s0,max(cs$S),cs$h,sta))
    r[[m$org]] <- list(mu0=mu0,s0=s0,S=cs$S,h=cs$h,alarme=cs$alarme)
  }
  cat("\n"); r
}

cusum_res$utiAB <- cusum_unit("utiAB","UTI A/B",
  list(list(org="esbl",lb="ESBL",   df=mdr_ab_esbl),
       list(org="kpc", lb="KPC",    df=mdr_ab_kpc),
       list(org="acin",lb="Acin.",  df=mdr_ab_acin)))
cusum_res$utic  <- cusum_unit("utic","UTI C",
  list(list(org="esbl",lb="ESBL",   df=mdr_uc_esbl),
       list(org="kpc", lb="KPC",    df=mdr_uc_kpc),
       list(org="acin",lb="Acin.",  df=mdr_uc_acin)))

# =============================================================================
# MODULO 4 - DIVERSIDADE TERAPEUTICA (Shannon H') — ordem cronologica
# =============================================================================

sec("MODULO 4 - DIVERSIDADE TERAPEUTICA Shannon H' (DOT mensal)")
cat("  H'>1.5 diversificado | 1.0-1.5 moderado | <1.0 concentrado\n\n")

# Meses disponiveis (todos os atbs × utiab como referencia), ordem cronologica
meses_ref <- merge_dot("cbp","utiab")$p
if(length(meses_ref)==0) meses_ref <- merge_dot("pip","utiab")$p
meses_ref <- meses_ref[order(sapply(meses_ref,sort_mes))]

if(length(meses_ref)>0) {
  # Cabecalho
  cat(sprintf("  %-14s",  "Unidade"))
  for(m in meses_ref) cat(sprintf("  %7s",m))
  cat("\n  ",paste(rep("-",16+9*length(meses_ref)),collapse=""),"\n")

  shan_res <- list()
  for(unit in UNIT_ORDEM) {
    H_vec <- sapply(meses_ref, function(mes) {
      vals <- sapply(ATBS, function(atb) {
        df <- merge_dot(atb,unit)
        v  <- df$v[df$p==mes]; if(length(v)) v[1] else 0
      })
      shannon_h(vals)
    })
    flag <- if(any(!is.na(H_vec)&H_vec<1.0,na.rm=TRUE))" !" else ""
    cat(sprintf("  %-14s",UNIT_NOMES[unit]%||%unit))
    for(h in H_vec) cat(sprintf("  %7s",if(is.na(h))"  —  " else sprintf("%.3f",h)))
    cat(flag,"\n")
    shan_res[[unit]] <- setNames(as.list(H_vec),meses_ref)
  }
  cat("\n  ! = ao menos 1 mes com H'<1.0 (uso muito concentrado)\n")
} else {
  cat("  Sem dados mensais de DOT disponíveis.\n")
  shan_res <- list()
}

# =============================================================================
# MODULO 5 - IC POISSON ACUMULADO 2026 (MDR)
# =============================================================================

sec("MODULO 5 - IC POISSON ACUMULADO 2026 - MDR (UTI A/B e UTI C)")

jan_ct_ab <- list(e=3,k=6,a=7); jan_rt_ab <- list(e=5.39,k=10.77,a=12.57)
pds_j <- sapply(names(jan_ct_ab), function(o){
  ct <- jan_ct_ab[[o]]; rt <- jan_rt_ab[[o]]
  if(ct==0||rt==0) NA else ct/(rt/1000)})
pd_jan <- round(mean(pds_j,na.rm=TRUE))

pd_ab <- c(pd_jan,475,556,585)
cnt_ab <- list(esbl=unlist(D$mdrMensal$utiAB$counts$esbl),
               kpc =unlist(D$mdrMensal$utiAB$counts$kpc),
               acin=unlist(D$mdrMensal$utiAB$counts$acin))
pd_uc  <- c(251,291,294)
cnt_uc <- list(esbl=unlist(D$mdrMensal$utic$counts$esbl)[2:4],
               kpc =unlist(D$mdrMensal$utic$counts$kpc)[2:4],
               acin=unlist(D$mdrMensal$utic$counts$acin)[2:4])
ORG_CP <- c(esbl="ESBL",kpc="KPC",acin="Acinetobacter")

cp_res <- list()
cp_unit <- function(cnts, pds, lbl) {
  cat(sprintf("\n  -- %s --\n  %-14s %8s %7s %7s  Poisson (prox.mes)\n",
              lbl,"Organismo","N_acum","IC95_l","IC95_u"))
  r <- list()
  for(o in names(ORG_CP)) {
    nv <- cnts[[o]]; Nt <- sum(nv,na.rm=TRUE); Pt <- sum(pds,na.rm=TRUE)
    cl <- qchisq(0.025,2*Nt)/(2*Pt/1000)
    cu <- qchisq(0.975,2*(Nt+1))/(2*Pt/1000)
    rt <- Nt/(Pt/1000)
    pp <- tryCatch({
      t_seq <- seq_along(nv)
      mod <- glm(nv~t_seq+offset(log(pds/1000)),family=poisson)
      nd  <- data.frame(t_seq=max(t_seq)+1, pds=mean(pds))
      pr  <- predict(mod,newdata=nd,type="link",se.fit=TRUE)
      sprintf("%.2f [%.2f-%.2f]",exp(pr$fit),
              exp(pr$fit-1.96*pr$se.fit),exp(pr$fit+1.96*pr$se.fit))
    },error=function(e)"indeterminado")
    cat(sprintf("  %-14s %8.2f %7.2f %7.2f  %s\n",ORG_CP[o],rt,cl,cu,pp))
    r[[o]] <- list(rate=rt,ci_l=cl,ci_u=cu)
  }
  cat("  IC Poisson exato (qui-quadrado) | /1000 pac-dia\n")
  r
}
cp_res$utiAB <- cp_unit(cnt_ab,pd_ab,"UTI A/B - jan-abr/26")
cp_res$utic  <- cp_unit(cnt_uc,pd_uc,"UTI C - fev-abr/26")

# =============================================================================
# MODULO 6 - CCF DOT -> MDR
# =============================================================================

sec("MODULO 6 - CCF DOT -> MDR (correlacao cruzada com lag 0-6 meses)")

# Pares prioritarios incluindo ceftriaxona e unidades de enfermaria
# CCF clinicamente relevante: ATB de espectro amplo x MDR que ele seleciona
PARES_CCF <- list(
  # UTIs — pares classicos de pressao seletiva
  list(atb="cbp", unit="utiab", mdr_u="utiAB", mdr_o="kpc",
       lb="Carbapenêmico x KPC (UTI A/B)"),
  list(atb="cbp", unit="utic",  mdr_u="utic",  mdr_o="kpc",
       lb="Carbapenêmico x KPC (UTI C)"),
  list(atb="pip", unit="utiab", mdr_u="utiAB", mdr_o="esbl",
       lb="Pip/Tazo x ESBL (UTI A/B)"),
  list(atb="pb",  unit="utiab", mdr_u="utiAB", mdr_o="acin",
       lb="Polimixina B x Acinetobacter (UTI A/B)"),
  # Ceftriaxona — enfermarias e EPM (maior problema identificado)
  list(atb="cef", unit="clin",  mdr_u="utiAB", mdr_o="esbl",
       lb="Ceftriaxona (Cl.Medica) x ESBL (UTI A/B)"),
  list(atb="cef", unit="epm",   mdr_u="utiAB", mdr_o="esbl",
       lb="Ceftriaxona (EPM) x ESBL (UTI A/B)"),
  list(atb="cef", unit="apto",  mdr_u="utiAB", mdr_o="esbl",
       lb="Ceftriaxona (Aptos) x ESBL (UTI A/B)"),
  # Glicopeptideo — relevante para MRSA / enterococo
  list(atb="gpp", unit="utiab", mdr_u="utiAB", mdr_o="kpc",
       lb="Glicopeptideo x KPC (UTI A/B)")
)

ccf_res <- list()

if(ccf_ok) {
  cat(sprintf("  %d meses simultaneos — CCF ATIVO\n\n",min(n_meses_dot,n_mdr)))
  cat(sprintf("  %-45s  n   lag* r*     Interpretacao\n","Par"))
  cat("  ",paste(rep("-",78),collapse=""),"\n")

  for(par in PARES_CCF) {
    df_dot <- merge_dot(par$atb, par$unit)
    df_mdr <- merge_mdr(par$mdr_u, par$mdr_o)
    if(nrow(df_dot)==0||nrow(df_mdr)==0) next

    mc <- intersect(df_dot$p, df_mdr$p)
    if(length(mc)<10){
      cat(sprintf("  %-45s  sobreposicao insuficiente (%d meses)\n",par$lb,length(mc)))
      next
    }
    x <- df_dot$v[match(mc,df_dot$p)]
    y <- df_mdr$v[match(mc,df_mdr$p)]
    xc <- scale(log1p(x)); yc <- scale(log1p(y)); nc <- length(xc)

    ccf_v <- sapply(0:6, function(lag)
      if(lag==0) cor(xc,yc,use="complete.obs")
      else cor(xc[1:(nc-lag)],yc[(lag+1):nc],use="complete.obs"))

    bl  <- which.max(ccf_v)-1
    br  <- max(ccf_v)
    ne  <- nc-bl-1
    sig <- abs(br) > qnorm(0.975)/sqrt(ne)

    interp <- if(bl==0&&sig) "associacao contemporanea *"
              else if(bl>0&&sig&&br>0) sprintf("DOT precede MDR +%d mes * (pressao seletiva?)",bl)
              else if(bl>0&&sig&&br<0) sprintf("DOT precede queda MDR +%d mes *",bl)
              else "(nao significativo)"

    cat(sprintf("  %-45s %2d  +%d  %5.3f  %s\n",par$lb,length(mc),bl,br,interp))
    ccf_res[[par$lb]] <- list(n=length(mc),lag=bl,r=br,sig=sig,ccf_vec=ccf_v)
  }
  cat("\n  * significativo (|r| > z0.975/sqrt(n-lag-1))\n")

} else {
  cat(sprintf("  Aguardando: %d/%d meses simultaneos\n",min(n_meses_dot,n_mdr),15))
  cat("  Progresso: [")
  cat(paste(rep("#",min(n_meses_dot,n_mdr)),collapse=""))
  cat(paste(rep(".",15-min(n_meses_dot,n_mdr)),collapse=""))
  cat("]\n\n")
  cat("  Pares priorizados quando ativo:\n")
  for(par in PARES_CCF) cat(sprintf("    - %s\n",par$lb))
}

# =============================================================================
# MODULO 7 - EXPORTACAO JSON
# =============================================================================

sec("MODULO 7 - EXPORTACAO husf_stats_output.json")

fmt_mk <- function(mk) {
  if(is.null(mk)||is.na(mk$tau)) return(list(tau=NULL,Z=NULL,p=NULL))
  list(tau=round(mk$tau,3), Z=round(mk$Z,3), p=round(mk$p.value,4),
       tendencia=if(mk$tau>0)"crescente" else "decrescente",
       sig=mk$p.value<0.05)
}
fmt_jp <- function(jp) {
  if(is.null(jp)||is.na(jp$jp)) return(list(jp=NULL,p=jp$p%||%NULL))
  list(jp_lbl=jp$jp_lbl, ci_l=jp$ci_l_lbl, ci_u=jp$ci_u_lbl,
       sb=round(jp$sb,3), sa=round(jp$sa,3), p=round(jp$p,4))
}

output <- list(
  meta=list(
    gerado_em=format(Sys.time(),"%Y-%m-%dT%H:%M:%S"),
    periodo=D$periodo, script="husf_stats.R v4.0",
    n_meses_dot=n_meses_dot, n_meses_mdr=n_mdr,
    hist_disponivel=!is.null(HIST), ccf_ativo=ccf_ok),

  dot_mensal_por_par = lapply(setNames(names(mk1b),names(mk1b)), function(k)
    list(mann_kendall=fmt_mk(mk1b[[k]]), joinpoint=fmt_jp(jp1b[[k]]))),

  dot_institucional = lapply(setNames(names(mk1c),names(mk1c)), function(atb)
    list(mann_kendall=fmt_mk(mk1c[[atb]]$mk), joinpoint=fmt_jp(mk1c[[atb]]$jp))),

  mdr_anual = lapply(setNames(names(mk2),names(mk2)), function(u)
    lapply(setNames(names(mk2[[u]]),names(mk2[[u]])), function(o)
      list(mann_kendall=fmt_mk(mk2[[u]][[o]]$mk),
           joinpoint=fmt_jp(mk2[[u]][[o]]$jp)))),

  mdr_mensal = lapply(setNames(names(mk2b),names(mk2b)), function(k)
    list(mann_kendall=fmt_mk(mk2b[[k]]$mk), joinpoint=fmt_jp(mk2b[[k]]$jp))),

  cusum = lapply(setNames(names(cusum_res),names(cusum_res)), function(u)
    lapply(setNames(names(cusum_res[[u]]),names(cusum_res[[u]])), function(o) {
      cs <- cusum_res[[u]][[o]]
      list(mu0=round(cs$mu0,2), s0=round(cs$s0,2), h=round(cs$h,2),
           S=round(cs$S,3), alarme=cs$alarme)})),

  ic_poisson_2026=lapply(setNames(names(cp_res),names(cp_res)), function(u)
    lapply(setNames(names(cp_res[[u]]),names(cp_res[[u]])), function(o)
      list(taxa=round(cp_res[[u]][[o]]$rate,2),
           ic95_l=round(cp_res[[u]][[o]]$ci_l,2),
           ic95_u=round(cp_res[[u]][[o]]$ci_u,2)))),

  ccf=if(ccf_ok) ccf_res else list(status="aguardando",n=min(n_meses_dot,n_mdr))
)

write(toJSON(output,auto_unbox=TRUE,pretty=TRUE,na="null"),
      file="husf_stats_output.json")

cat("\n  OK husf_stats_output.json salvo.\n")
cat(rep("=",70),"\n",sep="")
cat("  Concluido em",format(Sys.time(),"%H:%M:%S"),"\n")
cat(rep("=",70),"\n",sep="")
