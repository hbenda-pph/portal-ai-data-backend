#!/usr/bin/env bash
# Una sola vez en Cloud Shell, desde la raíz de este repo (carpeta backend/).
# Compute: platform-partners-des | Datos: pph-central + tenants
set -euo pipefail

COMPUTE_PROJECT="platform-partners-des"
DATA_CENTRAL="pph-central"
REGION="us-central1"
AR_REPO="portal"
SA_NAME="portal-backend"
SA_EMAIL="${SA_NAME}@${COMPUTE_PROJECT}.iam.gserviceaccount.com"

gcloud config set project "${COMPUTE_PROJECT}"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com

if ! gcloud artifacts repositories describe "${AR_REPO}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${AR_REPO}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Imágenes Cloud Run del Portal Analítico"
fi

if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  gcloud iam service-accounts create "${SA_NAME}" \
    --display-name="Portal Analítico Backend (Cloud Run)"
fi

gcloud projects add-iam-policy-binding "${COMPUTE_PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser" \
  --condition=None

bq add-iam-policy-binding \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.dataViewer" \
  "${DATA_CENTRAL}:settings"

mapfile -t TENANTS < <(
  bq query \
    --project_id="${COMPUTE_PROJECT}" \
    --use_legacy_sql=false \
    --format=csv \
    --max_rows=10000 \
    "SELECT DISTINCT company_project_id
     FROM \`${DATA_CENTRAL}.settings.companies\`
     WHERE company_project_id IS NOT NULL" \
    | tail -n +2
)

for TENANT in "${TENANTS[@]}"; do
  TENANT="$(echo "${TENANT}" | tr -d '\r')"
  [[ -z "${TENANT}" ]] && continue
  echo "IAM gold: ${TENANT}"
  bq add-iam-policy-binding \
    --member="serviceAccount:${SA_EMAIL}" \
    --role="roles/bigquery.dataViewer" \
    "${TENANT}:gold"
done

PROJECT_NUMBER="$(gcloud projects describe "${COMPUTE_PROJECT}" --format='value(projectNumber)')"
CB_SA="${PROJECT_NUMBER}@cloudbuild.gserviceaccount.com"

gcloud projects add-iam-policy-binding "${COMPUTE_PROJECT}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/run.admin" \
  --condition=None

gcloud projects add-iam-policy-binding "${COMPUTE_PROJECT}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/artifactregistry.writer" \
  --condition=None

gcloud iam service-accounts add-iam-policy-binding "${SA_EMAIL}" \
  --member="serviceAccount:${CB_SA}" \
  --role="roles/iam.serviceAccountUser"

echo
echo "Bootstrap listo. Desde esta carpeta (backend/):"
echo "  gcloud builds submit --config cloudbuild.yaml --project ${COMPUTE_PROJECT}"
