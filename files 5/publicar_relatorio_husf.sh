#!/bin/bash

# SCRIPT DE PUBLICAÇÃO AUTOMÁTICA - HUSF VIGILÂNCIA RESPIRATÓRIA
# Dr. Leandro - SCIH/CCIH
# Uso: ./publicar_relatorio_husf.sh

echo ""
echo "🏥 =================================================="
echo "   PUBLICAÇÃO AUTOMÁTICA - HUSF VIGILÂNCIA"
echo "   $(date '+%A, %d de %B de %Y - %H:%M')"
echo "🏥 =================================================="
echo ""

# Verificar se está na pasta correta
if [ ! -f "sistema_vigilancia_final.py" ]; then
    echo "❌ ERRO: Execute este script dentro da pasta ~/vigilancia_husf_braganca"
    echo "💡 Como corrigir:"
    echo "   cd ~/vigilancia_husf_braganca"
    echo "   ./publicar_relatorio_husf.sh"
    exit 1
fi

# 1. ATIVAR AMBIENTE
echo "🔧 Ativando ambiente Python..."
if [ ! -d "venv_vigilancia" ]; then
    echo "❌ ERRO: Ambiente virtual não encontrado"
    echo "💡 Execute: python3 -m venv venv_vigilancia"
    exit 1
fi

source venv_vigilancia/bin/activate
echo "✅ Ambiente ativado"

# 2. GERAR RELATÓRIO ATUALIZADO
echo ""
echo "📊 Gerando relatório com dados atuais..."
python3 sistema_vigilancia_final.py

if [ $? -ne 0 ]; then
    echo "❌ ERRO na geração do relatório"
    exit 1
fi
echo "✅ Relatório gerado com sucesso"

# 3. PREPARAR ARQUIVOS PARA GITHUB
echo ""
echo "📁 Preparando arquivos para publicação..."

# Verificar se os arquivos foram gerados
if [ ! -f "web/index.html" ]; then
    echo "❌ ERRO: HTML não foi gerado"
    exit 1
fi

# Copiar arquivos para raiz (GitHub Pages)
cp web/index.html .
cp web/README.md . 2>/dev/null || echo "README.md não encontrado, continuando..."

# Garantir que .gitignore existe
if [ ! -f ".gitignore" ]; then
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.pyc
venv_vigilancia/
.env

# Dados temporários
dados/
logs/
relatorios/

# Sistema
.DS_Store
EOF
fi

echo "✅ Arquivos preparados"

# 4. VERIFICAR GIT
echo ""
echo "🔄 Verificando repositório Git..."

if [ ! -d ".git" ]; then
    echo "⚠️  Repositório Git não inicializado"
    echo "💡 Iniciando Git..."
    git init
    echo "✅ Git inicializado"
    echo ""
    echo "📌 PRÓXIMO PASSO IMPORTANTE:"
    echo "   Conecte com GitHub executando:"
    echo "   git remote add origin https://github.com/SEUUSUARIO/vigilancia-husf.git"
    echo "   git branch -M main"
    echo ""
    echo "   Depois execute este script novamente."
    exit 0
fi

# Verificar se tem remote configurado
if ! git remote get-url origin &>/dev/null; then
    echo "⚠️  Repositório GitHub não configurado"
    echo "💡 Configure o repositório executando:"
    echo "   git remote add origin https://github.com/SEUUSUARIO/vigilancia-husf.git"
    echo "   git branch -M main"
    exit 0
fi

# 5. COMMIT E PUSH
echo "📤 Publicando no GitHub..."

# Adicionar todos os arquivos
git add -A

# Verificar se tem algo para commitar
if git diff --staged --quiet; then
    echo "ℹ️  Nenhuma alteração detectada - relatório já está atualizado"
    echo "🌐 Acesse: $(git remote get-url origin | sed 's/\.git$//' | sed 's/github\.com\//github.io\//')/$(basename $(pwd))/"
    exit 0
fi

# Fazer commit
TIMESTAMP=$(date '+%d/%m/%Y %H:%M')
git commit -m "📊 Relatório Vigilância HUSF - $TIMESTAMP

✅ Dados atualizados InfoGripe/Fiocruz
🔬 VPN ≥95% = Liberação Segura  
🏥 HUSF Bragança Paulista - Dr. Leandro CCIH"

# Push para GitHub
echo "🚀 Enviando para GitHub..."
git push origin main

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ =================================================="
    echo "   PUBLICAÇÃO CONCLUÍDA COM SUCESSO!"
    echo "✅ =================================================="
    echo ""
    
    # Determinar URL do GitHub Pages
    REPO_URL=$(git remote get-url origin)
    USER=$(echo $REPO_URL | sed 's/.*github\.com[:/]\([^/]*\).*/\1/')
    REPO=$(basename $REPO_URL .git)
    GITHUB_PAGES_URL="https://$USER.github.io/$REPO/"
    
    echo "🌐 SEU RELATÓRIO ESTÁ DISPONÍVEL EM:"
    echo "   $GITHUB_PAGES_URL"
    echo ""
    echo "📱 CARACTERÍSTICAS:"
    echo "   ✅ Responsivo (mobile/tablet/desktop)"
    echo "   ✅ Atualização automática a cada 30min"
    echo "   ✅ VPN ≥95% = Liberação Segura"
    echo "   ✅ Dados reais InfoGripe/Fiocruz"
    echo ""
    echo "📧 COMPARTILHE COM AS GESTÕES:"
    echo "   $GITHUB_PAGES_URL"
    echo ""
    echo "📞 SUPORTE TÉCNICO:"
    echo "   Dr. Leandro - SCIH/CCIH HUSF"
    echo ""
    echo "🔄 PRÓXIMA EXECUÇÃO:"
    echo "   ./publicar_relatorio_husf.sh"
    echo "   (Recomendado: quinzenalmente)"
    echo ""
    
    # Tentar abrir no navegador (macOS)
    if command -v open &> /dev/null; then
        echo "🖥️  Abrindo no navegador..."
        open "$GITHUB_PAGES_URL"
    fi
    
else
    echo ""
    echo "❌ ERRO no push para GitHub"
    echo "💡 Possíveis soluções:"
    echo "   1. Verificar conexão com internet"
    echo "   2. Verificar autenticação GitHub"
    echo "   3. Executar: git push origin main --force"
    echo ""
fi

echo ""
echo "📊 Relatório local salvo em:"
echo "   • HTML: web/index.html" 
echo "   • JSON: dados/vigilancia_final_*.json"
echo "   • MD: relatorios/relatorio_final_*.md"
echo ""
