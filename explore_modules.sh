#!/bin/bash
# PHASE 1: Module Exploration Starter Kit
# Run this script to explore all three 3SIAS modules

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║        3SIAS Module Exploration - Phase 1 Starter Kit         ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

MODULES=("machine-simulator" "digital-twin" "predictive-maintenance")
ROOT_DIR=$(pwd)

for module in "${MODULES[@]}"; do
    echo ""
    echo "═══════════════════════════════════════════════════════════════"
    echo "📦 Exploring: $module"
    echo "═══════════════════════════════════════════════════════════════"
    
    MODULE_PATH="modules/$module"
    
    if [ ! -d "$MODULE_PATH" ]; then
        echo "❌ Module directory not found: $MODULE_PATH"
        continue
    fi
    
    cd "$MODULE_PATH"
    
    echo ""
    echo "📋 Module Structure:"
    echo "───────────────────────────────────────────────────────────────"
    ls -la | grep -E "^d|\.py$|\.md$|\.txt$" | awk '{print $9}'
    
    echo ""
    echo "📖 README.md (first 50 lines):"
    echo "───────────────────────────────────────────────────────────────"
    if [ -f "README.md" ]; then
        head -50 README.md
    else
        echo "⚠️  README.md not found"
    fi
    
    echo ""
    echo "📚 Requirements:"
    echo "───────────────────────────────────────────────────────────────"
    if [ -f "requirements.txt" ]; then
        cat requirements.txt
    else
        echo "⚠️  requirements.txt not found"
    fi
    
    echo ""
    echo "🐍 Python Files (main functions):"
    echo "───────────────────────────────────────────────────────────────"
    grep -r "^def " --include="*.py" . | head -15 || echo "No Python files found"
    
    echo ""
    echo "🔍 Python Files Found:"
    echo "───────────────────────────────────────────────────────────────"
    find . -name "*.py" -type f | head -10
    
    echo ""
    echo "📝 git log (last 5 commits):"
    echo "───────────────────────────────────────────────────────────────"
    git log --oneline -5 2>/dev/null || echo "⚠️  Not a git repo or git not available"
    
    cd "$ROOT_DIR"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ Phase 1 Exploration Complete!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📚 Next Steps:"
echo "1. Read each module's README.md in detail"
echo "2. Understand module capabilities and APIs"
echo "3. Review Python files to see available functions"
echo "4. Install dependencies: pip install -r requirements.txt (in each module)"
echo "5. Test loading modules in Python REPL"
echo ""
echo "💡 Test Module Loading:"
echo "───────────────────────────────────────────────────────────────"
cat << 'EOF'
python3 << 'PYTHON'
from app.modules_integration import ModuleRegistry, init_modules
from flask import Flask

app = Flask(__name__)
init_modules(app)

print("📦 Loaded Modules:")
for module_name in ModuleRegistry.list_modules():
    module = ModuleRegistry.get(module_name)
    print(f"  ✓ {module_name}: {type(module)}")
    if hasattr(module, 'get_status'):
        print(f"    Status: {module.get_status()}")

PYTHON
EOF
echo ""
echo "For more information, see: DEVELOPMENT_ROADMAP.md"
