# 🌐 **GUIA PUBLICAÇÃO GITHUB PAGES - HUSF VIGILÂNCIA**

## 📋 **CONFIGURAÇÃO ÚNICA (FAZER 1 VEZ APENAS)**

### **1. CRIAR REPOSITÓRIO NO GITHUB (5 minutos)**

```bash
# No seu Mac, criar repositório local
cd ~/vigilancia_husf_braganca
git init
```

**No GitHub.com:**
1. ➕ **New Repository**
2. 📝 Nome: `vigilancia-husf` (ou outro nome de sua escolha)
3. ✅ Public (para GitHub Pages funcionar)
4. ✅ Add README
5. 🔗 Copiar a URL: `https://github.com/SEUUSUARIO/vigilancia-husf.git`

### **2. CONECTAR LOCAL COM GITHUB (2 minutos)**

```bash
# Conectar com GitHub
git remote add origin https://github.com/SEUUSUARIO/vigilancia-husf.git
git branch -M main

# Configurar seu usuário (se ainda não fez)
git config --global user.email "seuemail@husf.com.br"
git config --global user.name "Dr. Leandro HUSF"
```

### **3. ATIVAR GITHUB PAGES (1 minuto)**

**No GitHub.com > seu repositório:**
1. ⚙️ **Settings** (aba no topo)
2. 📄 **Pages** (menu lateral esquerdo)
3. 🔧 **Source**: Deploy from a branch
4. 🌿 **Branch**: `main`
5. 📁 **Folder**: `/ (root)`
6. 💾 **Save**

**🎉 Seu site estará em:** `https://SEUUSUARIO.github.io/vigilancia-husf/`

---

## 🚀 **PUBLICAÇÃO MENSAL AUTOMÁTICA (3 minutos)**

### **SCRIPT DE PUBLICAÇÃO COMPLETA:**

```bash
# Criar script de publicação automática
cd ~/vigilancia_husf_braganca

cat > publicar_relatorio.sh << 'EOF'
#!/bin/bash
echo "🏥 PUBLICANDO RELATÓRIO HUSF - $(date '+%B %Y')"

# 1. Ativar ambiente
source venv_vigilancia/bin/activate

# 2. Gerar novo relatório
python3 sistema_vigilancia_final.py

# 3. Preparar arquivos para GitHub
echo "📁 Preparando arquivos..."

# Copiar arquivos essenciais para raiz (GitHub Pages)
cp web/index.html .
cp web/README.md .

# 4. Commit e push
echo "🔄 Publicando no GitHub..."
git add -A
git commit -m "📊 Relatório Vigilância $(date '+%d/%m/%Y %H:%M')"
git push origin main

echo "✅ PUBLICAÇÃO CONCLUÍDA!"
echo "🌐 Acesse: https://SEUUSUARIO.github.io/vigilancia-husf/"
echo "📱 Mobile-friendly e auto-atualiza"
EOF

chmod +x publicar_relatorio.sh
```

### **EXECUÇÃO MENSAL SIMPLES:**

```bash
# Executar publicação (uma linha apenas!)
cd ~/vigilancia_husf_braganca && ./publicar_relatorio.sh
```

---

## 📱 **RESULTADO FINAL**

### **URL PÚBLICA:**
```
🌐 https://SEUUSUARIO.github.io/vigilancia-husf/
```

**Características:**
- ✅ **Responsivo** (mobile, tablet, desktop)
- ✅ **Atualização automática** a cada 30min na página
- ✅ **Design moderno** com Bootstrap 5
- ✅ **Cores intuitivas** (verde=seguro, amarelo=cautela, vermelho=RT-PCR)
- ✅ **Dados em tempo real** do InfoGripe/Fiocruz
- ✅ **Critério otimizado** VPN ≥95%

### **COMPARTILHAMENTO:**
```
📧 EMAIL para gestões:
Assunto: Relatório Vigilância Respiratória - HUSF
Link: https://SEUUSUARIO.github.io/vigilancia-husf/

📱 WHATSAPP:
"Novo relatório vigilância respiratória disponível:
https://SEUUSUARIO.github.io/vigilancia-husf/"

📋 QR CODE:
[Gerar em qualquer site de QR code com a URL]
```

---

## 🔧 **CUSTOMIZAÇÕES OPCIONAIS**

### **1. DOMÍNIO PERSONALIZADO (Opcional):**

Se o hospital tiver domínio próprio:

**No GitHub Pages > Custom Domain:**
- Digite: `vigilancia.husf.com.br` (exemplo)
- Configurar DNS no provedor do hospital

### **2. SENHA DE ACESSO (Opcional):**

```javascript
// Adicionar no início do HTML (básico)
<script>
const senha = prompt("Digite a senha CCIH:");
if (senha !== "HUSF2026") {
    document.body.innerHTML = "<h1>Acesso negado</h1>";
}
</script>
```

### **3. NOTIFICAÇÕES AUTOMÁTICAS:**

```bash
# Adicionar no script de publicação
# Enviar email automático após publicação
curl -X POST \
  https://api.emailjs.com/api/v1.0/email/send \
  -H 'Content-Type: application/json' \
  -d '{
    "service_id": "SEUSERVICO",
    "template_id": "SEUTEMPLATE", 
    "user_id": "SEUUSERID",
    "template_params": {
        "message": "Novo relatório vigilância disponível",
        "url": "https://SEUUSUARIO.github.io/vigilancia-husf/"
    }
}'
```

---

## 📊 **ESTRUTURA DO RELATÓRIO PUBLICADO**

### **VISUALIZAÇÃO WEB INCLUIRÁ:**

```
📋 HEADER
├── 🏥 Título e logo HUSF
├── 📅 Data/hora última atualização  
└── 👨‍⚕️ Dr. Leandro CCIH/SCIH

📊 CENÁRIO NACIONAL
├── 📈 Total casos SRAG
├── ⚕️ Casos positivos
├── 📉 Taxa positividade
└── 🗓️ Semana epidemiológica

🎯 CRITÉRIO DECISÃO
├── VPN ≥95% = 🟢 LIBERAÇÃO SEGURA
├── VPN 90-95% = 🟡 CAUTELA
└── VPN <90% = 🔴 RT-PCR

🦠 ORIENTAÇÕES POR PATÓGENO
├── COVID-19: [VPN] [ORIENTAÇÃO]
├── Influenza A: [VPN] [ORIENTAÇÃO]  
├── Influenza B: [VPN] [ORIENTAÇÃO]
├── VSR: [VPN] [ORIENTAÇÃO]
├── Rinovírus: [VPN] [ORIENTAÇÃO]
└── Outros: [VPN] [ORIENTAÇÃO]

📞 CONTATO TÉCNICO
└── Dr. Leandro CCIH/SCIH
```

---

## ⚡ **WORKFLOW MENSAL OTIMIZADO**

### **ROTINA QUINZENAL COMPLETA:**

```bash
# APENAS 1 COMANDO para tudo:
cd ~/vigilancia_husf_braganca && ./publicar_relatorio.sh

# Isso fará AUTOMATICAMENTE:
# 1. ✅ Gerar novo relatório com dados atuais
# 2. ✅ Criar HTML responsivo
# 3. ✅ Publicar no GitHub Pages  
# 4. ✅ Notificar conclusão
# 5. ✅ Fornecer URL para compartilhar
```

### **RESULTADO IMEDIATO:**
- **3 minutos**: Relatório publicado na web
- **URL única**: Accessível por qualquer dispositivo
- **Histórico**: Versões anteriores salvas no GitHub
- **Compartilhamento**: Link direto para gestões

---

## 📱 **ACESSO PELAS GESTÕES**

### **INSTRUÇÕES PARA GESTORES:**

```
📧 EMAIL PADRÃO:

Assunto: Acesso ao Sistema de Vigilância Respiratória

Prezados gestores,

O relatório de vigilância respiratória está disponível em:
🌐 https://SEUUSUARIO.github.io/vigilancia-husf/

✅ Atualização quinzenal automática
✅ Acesso via qualquer dispositivo
✅ Orientações baseadas em dados científicos
✅ VPN ≥95% = liberação segura

Dúvidas: Dr. Leandro CCIH/SCIH

---
Sistema HUSF Bragança Paulista
```

### **VANTAGENS PARA GESTÕES:**
- 📱 **Mobile-first**: Perfeito em smartphones
- 🔄 **Sempre atualizado**: Dados mais recentes
- 📊 **Visual intuitivo**: Cores e ícones claros
- 📞 **Contato direto**: Link para Dr. Leandro
- 💾 **Sem instalação**: Funciona no navegador

---

## 🎯 **CHECKLIST DE IMPLEMENTAÇÃO**

### **✅ CONFIGURAÇÃO INICIAL (fazer 1 vez):**
```
□ Criar conta GitHub (se não tem)
□ Criar repositório vigilancia-husf
□ Conectar repositório local
□ Ativar GitHub Pages  
□ Configurar script publicar_relatorio.sh
□ Testar primeira publicação
```

### **✅ ROTINA MENSAL (3 minutos):**
```
□ cd ~/vigilancia_husf_braganca
□ ./publicar_relatorio.sh
□ Aguardar conclusão
□ Compartilhar URL com gestões
□ Verificar funcionamento em mobile
```

---

## 🚀 **PRÓXIMOS PASSOS RECOMENDADOS**

1. **HOJE**: Configurar GitHub Pages (15 min)
2. **HOJE**: Primeira publicação de teste (5 min)
3. **HOJE**: Compartilhar URL com gestões (2 min)
4. **1ª QUINZENA/ABRIL**: Primeira publicação oficial (3 min)
5. **MENSAL**: Rotina automatizada de publicação

---

**🎉 RESULTADO FINAL:**

✅ **Relatórios acessíveis 24/7** para todas as gestões  
✅ **Critério científico otimizado** VPN ≥95% = seguro  
✅ **Publicação automática** em 3 minutos  
✅ **Design responsivo** para todos dispositivos  
✅ **Zero custos** (GitHub Pages gratuito)  
✅ **URL profissional** para compartilhamento  

**A vigilância respiratória do HUSF agora está na era digital! 🚀**
