#!/bin/bash

# PUBLICAÇÃO HUSF - VERSÃO DINÂMICA ATUALIZADA
# Sistema que busca dados mais recentes automaticamente

echo "🏥 Publicando relatório HUSF com dados dinâmicos - $(date '+%d/%m/%Y %H:%M')"

# Verificar se está na pasta correta
if [ ! -f "sistema_vigilancia_dinamico.py" ]; then
    echo "❌ ERRO: Execute na pasta ~/vigilancia_husf_braganca"
    echo "💡 Arquivo sistema_vigilancia_dinamico.py não encontrado"
    exit 1
fi

# Ativar ambiente virtual
source venv_vigilancia/bin/activate

# Gerar relatório com dados dinâmicos
echo "📊 Gerando relatório com dados mais recentes disponíveis..."
python3 sistema_vigilancia_dinamico.py

if [ $? -ne 0 ]; then
    echo "❌ Erro na execução do sistema dinâmico"
    echo "💡 Tentando sistema original como fallback..."
    python3 sistema_vigilancia_final.py
fi

# Copiar HTML para raiz
if [ -f "web/index.html" ]; then
    cp web/index.html .
    echo "✅ HTML copiado para raiz"
else
    echo "❌ web/index.html não encontrado"
    exit 1
fi

# Git add, commit e push
echo "📤 Enviando para GitHub..."
git add -A

if git diff --staged --quiet; then
    echo "ℹ️  Nenhuma alteração detectada"
else
    git commit -m "📊 Relatório HUSF DINÂMICO - $(date '+%d/%m/%Y %H:%M')

✅ Sistema com busca de dados mais recentes
🔄 Dados atualizados automaticamente do InfoGripe
📈 SE mais atual disponível processada
🌐 Relatório responsivo atualizado"
    
    git push origin main
    
    if [ $? -eq 0 ]; then
        echo "✅ Push realizado com sucesso!"
    else
        echo "❌ Erro no push"
        exit 1
    fi
fi

echo ""
echo "🎉 =================================================="
echo "   PUBLICAÇÃO DINÂMICA CONCLUÍDA!"
echo "🎉 =================================================="
echo ""
echo "✅ Sistema executado com dados mais atuais"
echo "🌐 Acesse: https://doutorleandromendes.github.io/vigilancia_husf/"
echo "📊 Dados: SE mais recente disponível"
echo "🔄 Sistema busca automaticamente novos dados"
echo ""
echo "📧 URL para gestões:"
echo "   https://doutorleandromendes.github.io/vigilancia_husf/"
echo ""
