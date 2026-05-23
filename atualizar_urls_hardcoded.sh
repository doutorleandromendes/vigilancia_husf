#!/bin/bash

# CORREÇÃO RÁPIDA: ATUALIZAR URLs HARDCODED
echo "🔧 ATUALIZANDO URLs HARDCODED PARA SE 15-19..."

cd ~/vigilancia_husf_braganca

# Backup
cp sistema_vigilancia_automatico_FINAL.py sistema_BACKUP_urls_antigas.py

echo "📋 URLs ANTIGAS:"
grep -n "Resumo_InfoGripe_2026" sistema_vigilancia_automatico_FINAL.py

echo ""
echo "🔄 Aplicando correções..."

# Método 1: Substituição direta das URLs
python3 -c "
# Ler arquivo
with open('sistema_vigilancia_automatico_FINAL.py', 'r') as f:
    conteudo = f.read()

# Mapeamento de substituições (SE antigo -> SE novo)
substituicoes = {
    'Resumo_InfoGripe_2026_14_0.pdf': 'Resumo_InfoGripe_2026_19.pdf',
    'Resumo_InfoGripe_2026_13_0.pdf': 'Resumo_InfoGripe_2026_18.pdf', 
    'Resumo_InfoGripe_2026_12_0.pdf': 'Resumo_InfoGripe_2026_17.pdf',
    'Resumo_InfoGripe_2026_11_0.pdf': 'Resumo_InfoGripe_2026_16.pdf'
}

# Aplicar substituições
for antigo, novo in substituicoes.items():
    if antigo in conteudo:
        conteudo = conteudo.replace(antigo, novo)
        print(f'✅ {antigo} → {novo}')
    else:
        print(f'❌ {antigo} não encontrado')

# Salvar arquivo modificado
with open('sistema_vigilancia_automatico_FINAL.py', 'w') as f:
    f.write(conteudo)

print('✅ URLs atualizadas!')
"

echo ""
echo "📋 URLs NOVAS:"
grep -n "Resumo_InfoGripe_2026" sistema_vigilancia_automatico_FINAL.py

echo ""
echo "🧪 Testando sistema com URLs atualizadas..."

# Executar sistema
if python3 sistema_vigilancia_automatico_FINAL.py > teste_urls_novas.log 2>&1; then
    
    # Verificar qual SE foi encontrada
    SE_ENCONTRADA=$(grep -o "SE [0-9]\+/2026" teste_urls_novas.log | tail -1 | grep -o "[0-9]\+")
    
    if [ "$SE_ENCONTRADA" ]; then
        echo "✅ SUCESSO! SE ENCONTRADA: $SE_ENCONTRADA"
        
        if [ "$SE_ENCONTRADA" -ge "18" ]; then
            echo "🎯 EXCELENTE! SE $SE_ENCONTRADA é muito atual"
        elif [ "$SE_ENCONTRADA" -ge "16" ]; then
            echo "✅ BOM! SE $SE_ENCONTRADA é melhor que SE 14"
        fi
        
        # Mostrar dados relevantes
        echo ""
        echo "📊 DADOS EXTRAÍDOS:"
        grep -E "(SE:|Método:|COVID19:|INFLUENZA_A:|VSR:)" teste_urls_novas.log | head -6
        
        # Publicar
        echo ""
        echo "📤 Publicando SE atualizada..."
        cp web/index.html index.html
        git add .
        git commit -m "📊 HUSF - URLs atualizadas SE $SE_ENCONTRADA - $(date '+%d/%m/%Y %H:%M')"
        git push origin main
        
        echo ""
        echo "🎉 SUCESSO TOTAL!"
        echo "🌐 Site: https://doutorleandromendes.github.io/vigilancia_husf/"
        echo "📊 SE atualizada de 14 para $SE_ENCONTRADA"
        
    else
        echo "❌ Não conseguiu identificar SE nos logs"
        echo ""
        echo "📋 LOG DE ERRO:"
        tail -10 teste_urls_novas.log
    fi
    
else
    echo "❌ SISTEMA FALHOU - Restaurando backup"
    cp sistema_BACKUP_urls_antigas.py sistema_vigilancia_automatico_FINAL.py
    
    echo ""
    echo "📋 LOG DE ERRO:"
    tail -15 teste_urls_novas.log
fi

echo ""
echo "📋 ARQUIVO DE LOG SALVO: teste_urls_novas.log"
