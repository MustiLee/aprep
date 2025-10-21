## KURULUM REHBERİ

### 1. Sistem Gereksinimleri
- Python 3.10 veya üzeri
- pip (Python package manager)
- Anthropic API key

### 2. Kurulum Adımları

#### Adım 1: Repository'yi klonla veya indir

```bash
cd /path/to/Aprep/backend
```

#### Adım 2: Python bağımlılıklarını kur

```bash
# Virtual environment oluştur (önerilen)
python3 -m venv venv

# Virtual environment'ı aktive et
# macOS/Linux:
source venv/bin/activate
# Windows:
# venv\Scripts\activate

# Bağımlılıkları kur
pip install -r requirements.txt
```

#### Adım 3: Environment variables ayarla

```bash
# .env dosyası oluştur
cp .env.example .env

# .env dosyasını düzenle ve API key'ini ekle
# ANTHROPIC_API_KEY=your_actual_api_key_here
```

#### Adım 4: Data klasörlerini oluştur

```bash
# Otomatik oluşturulacak ama manuel de yapabilirsin
mkdir -p data/ced data/templates data/misconceptions
```

### 3. Kurulumu Test Et

```bash
# Unit testleri çalıştır
pytest tests/unit/ -v

# Integration testleri çalıştır
pytest tests/integration/ -v

# Tüm testler
pytest tests/ -v

# Coverage ile
pytest --cov=src tests/
```

### 4. Example Script'leri Çalıştır

```bash
# Basit example
python example.py

# Komple workflow example
python example_complete.py
```

### 5. Olası Sorunlar ve Çözümler

#### Problem: ModuleNotFoundError
```bash
# Çözüm: PYTHONPATH'i ayarla
export PYTHONPATH="${PYTHONPATH}:${PWD}"
```

#### Problem: Anthropic API hatası
```bash
# .env dosyasını kontrol et
cat .env
# API key'in doğru olduğundan emin ol
```

#### Problem: PDF parsing hatası (CED Parser için)
```bash
# pdfplumber ve PyPDF2'nin kurulu olduğundan emin ol
pip install pdfplumber PyPDF2
```

### 6. Development Ortamı

#### Code formatting
```bash
black src/ tests/
```

#### Type checking
```bash
mypy src/
```

#### Linting
```bash
ruff check src/
```

### 7. Proje Yapısı

```
backend/
├── src/
│   ├── agents/          # Agent implementations
│   │   ├── ced_parser.py
│   │   ├── template_crafter.py
│   │   ├── parametric_generator.py
│   │   ├── solution_verifier.py
│   │   └── master_orchestrator.py
│   ├── api/             # FastAPI endpoints
│   │   ├── main.py
│   │   └── routers/
│   │       ├── templates.py
│   │       ├── variants.py
│   │       ├── verification.py
│   │       └── workflows.py
│   ├── core/            # Core utilities
│   │   ├── config.py
│   │   ├── logger.py
│   │   └── exceptions.py
│   ├── models/          # Data models
│   │   ├── template.py
│   │   └── variant.py
│   └── utils/           # Utilities
│       └── database.py
├── tests/               # Test suite
├── data/               # Data storage
├── requirements.txt    # Dependencies
├── .env.example       # Config template
└── README.md          # Documentation
```

### 8. Hızlı Başlangıç

En basit kullanım:

```python
from src.agents import TemplateCrafter, ParametricGenerator
from src.utils.database import TemplateDatabase, VariantDatabase

# Template oluştur
crafter = TemplateCrafter()
template = crafter.create_template({
    "course_id": "ap_calculus_bc",
    "topic_id": "derivatives",
    "learning_objectives": ["Calculate derivatives"],
    "misconceptions": ["Forgot power rule"]
})

# Variant'lar oluştur
generator = ParametricGenerator()
variants = generator.generate_batch(template, count=10)

# Kaydet
db = VariantDatabase()
db.save_batch(variants)
```

### 9. Yardım

Sorun olursa:
1. `pytest tests/ -v` ile testleri çalıştır
2. `python example_complete.py` ile örneği dene
3. Log'ları kontrol et
4. README.md'yi incele
