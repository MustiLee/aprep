# Aprep AI Agent System - Quick Start Guide

Bu rehber sistemı 5 dakikada çalıştırmanızı sağlar.

---

## Seçenek 1: Manuel Başlatma (Önerilen - İlk Deneme)

### 1. Gereksinimler

- Python 3.10+
- Anthropic API key

### 2. Kurulum

```bash
cd /Users/mustafayildirim/Documents/Personal\ Documents/Projects/Aprep/backend

# .env dosyasını düzenle
cp .env.example .env
nano .env  # ANTHROPIC_API_KEY'inizi ekleyin

# API'yi başlat
./start_api.sh
```

### 3. API Test Et

Yeni bir terminal açın:

```bash
# Health check
curl http://localhost:8000/health

# API status
curl http://localhost:8000/api/v1/status

# Tarayıcıda API docs
open http://localhost:8000/docs
```

### 4. İlk Template Oluştur

```bash
curl -X POST http://localhost:8000/api/v1/templates/ \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "demo_001",
    "course_id": "ap_calculus_bc",
    "unit_id": "u2_differentiation",
    "topic_id": "t2_power_rule",
    "learning_objectives": ["Apply power rule to polynomial functions"],
    "difficulty_target": [0.4, 0.7],
    "calculator_policy": "No-Calc",
    "misconceptions": ["Forgot to multiply by exponent"]
  }'
```

### 5. Variant Üret

```bash
# Template ID'yi yukarıdaki response'dan al (örn: tmpl_apcalc_bc_u2_power_001_v1)

curl -X POST http://localhost:8000/api/v1/variants/generate \
  -H "Content-Type: application/json" \
  -d '{
    "template_id": "BURAYA_TEMPLATE_ID_YAZIN",
    "count": 5,
    "seed_start": 0
  }'
```

### 6. Verify Et

```bash
# Variant ID'yi yukarıdaki response'dan al

curl -X POST http://localhost:8000/api/v1/verification/verify \
  -H "Content-Type: application/json" \
  -d '{
    "variant_id": "BURAYA_VARIANT_ID_YAZIN"
  }'
```

### 7. Otomatik Test

Tüm workflow'u test et:

```bash
./test_api.sh
```

---

## Seçenek 2: Docker ile Başlatma

### 1. Gereksinimler

- Docker
- Docker Compose
- Anthropic API key

### 2. Başlatma

```bash
cd /Users/mustafayildirim/Documents/Personal\ Documents/Projects/Aprep/backend

# .env dosyasını düzenle
cp .env.example .env
nano .env  # ANTHROPIC_API_KEY'inizi ekleyin

# Tüm servisleri başlat
docker-compose up -d

# Logları izle
docker-compose logs -f api
```

### 3. Servislere Erişim

- **API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs
- **PostgreSQL**: localhost:5432 (aprep/aprep)
- **pgAdmin**: http://localhost:5050 (admin@aprep.com/admin)
- **Redis**: localhost:6379

### 4. Test Et

```bash
# Health check
curl http://localhost:8000/health

# Otomatik test
./test_api.sh
```

### 5. Durdurma

```bash
# Servisleri durdur
docker-compose down

# Veritabanı ile birlikte durdur (DİKKAT: Veri silinir!)
docker-compose down -v
```

---

## Seçenek 3: Python Directly (Development)

```bash
# Virtual environment oluştur
python3 -m venv venv
source venv/bin/activate

# Dependencies kur
pip install -r requirements.txt

# .env oluştur
cp .env.example .env
# Edit .env and add ANTHROPIC_API_KEY

# Data klasörleri oluştur
mkdir -p data/ced data/templates data/misconceptions

# API'yi başlat
uvicorn src.api.main:app --reload
```

---

## API Endpoints

### Templates

```bash
# Create template
POST /api/v1/templates/

# Get template
GET /api/v1/templates/{template_id}

# List templates
GET /api/v1/templates/?course_id=ap_calculus_bc

# Delete template
DELETE /api/v1/templates/{template_id}
```

### Variants

```bash
# Generate variants
POST /api/v1/variants/generate

# Get variant
GET /api/v1/variants/{variant_id}

# List variants
GET /api/v1/variants/?template_id=xxx

# Delete variant
DELETE /api/v1/variants/{variant_id}
```

### Verification

```bash
# Verify single variant
POST /api/v1/verification/verify

# Verify batch
POST /api/v1/verification/verify/batch
```

### Workflows

```bash
# Execute workflow
POST /api/v1/workflows/execute
```

---

## Örnek Workflow

### Python SDK Örneği

```python
import requests

API_URL = "http://localhost:8000"

# 1. Template oluştur
template_data = {
    "task_id": "demo_001",
    "course_id": "ap_calculus_bc",
    "unit_id": "u2_differentiation",
    "topic_id": "t2_power_rule",
    "learning_objectives": ["Apply power rule"],
    "difficulty_target": [0.4, 0.7],
    "calculator_policy": "No-Calc",
    "misconceptions": ["Forgot to multiply by exponent"]
}

response = requests.post(f"{API_URL}/api/v1/templates/", json=template_data)
template = response.json()
template_id = template["template_id"]

print(f"Template created: {template_id}")

# 2. Variant'lar üret
variant_data = {
    "template_id": template_id,
    "count": 10,
    "seed_start": 0
}

response = requests.post(f"{API_URL}/api/v1/variants/generate", json=variant_data)
variants = response.json()

print(f"Generated {len(variants)} variants")

# 3. İlk variant'ı verify et
variant_id = variants[0]["id"]

response = requests.post(
    f"{API_URL}/api/v1/verification/verify",
    json={"variant_id": variant_id}
)

verification = response.json()
print(f"Verification: {verification['verification_status']}")
print(f"Confidence: {verification['consensus']['confidence']}")
```

---

## Troubleshooting

### API başlamıyor

```bash
# Port 8000 kullanımda mı?
lsof -i :8000

# Dependencies kurulu mu?
pip install -r requirements.txt

# .env dosyası var mı?
ls -la .env
```

### Template oluşturulmuyor

```bash
# ANTHROPIC_API_KEY set mi?
cat .env | grep ANTHROPIC

# API logları
# Manuel: Terminal'de görünür
# Docker: docker-compose logs -f api
```

### Variant generate olmuyor

```bash
# Template ID doğru mu kontrol et
curl http://localhost:8000/api/v1/templates/

# Data klasörleri var mı?
ls -la data/templates/
```

---

## Yararlı Komutlar

```bash
# API durumu
curl http://localhost:8000/health

# Template listesi
curl http://localhost:8000/api/v1/templates/ | python3 -m json.tool

# Variant listesi
curl http://localhost:8000/api/v1/variants/ | python3 -m json.tool

# API docs (tarayıcı)
open http://localhost:8000/docs
```

---

## Next Steps

1. ✅ API çalıştır ve test et
2. ✅ İlk template oluştur
3. ✅ Variant'lar üret
4. ✅ Verification test et
5. 📖 Full documentation: `DEPLOYMENT.md`
6. 🐳 Production deployment: `docker-compose -f docker-compose.prod.yml up`

---

**Quick Help:**

- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health
- PostgreSQL: localhost:5432 (aprep/aprep)

**Need Help?** Check `README.md`, `SETUP.md`, or `DEPLOYMENT.md`
