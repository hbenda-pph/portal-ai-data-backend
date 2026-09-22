#!/usr/bin/env bash
# Una sola vez en Cloud Shell, desde la raíz de este repo (carpeta backend/).
# Compute: platform-partners-des | Datos: pph-central + tenants
#
# Dataset IAM (bq add-iam-policy-binding) no está allowlisted en esta org.
# Se usa ACL clásica del dataset: role READER + userByEmail de la SA.
set -euo pipefail

COMPUTE_PROJECT="platform-partners-des"
DATA_CENTRAL="pph-central"
APP="portal-ai-data-backend"
REGION="us-central1"
SA_EMAIL="etl-servicetitan@${COMPUTE_PROJECT}.iam.gserviceaccount.com"

grant_dataset_reader() {
  local dataset="$1"
  python3 - "${dataset}" "${SA_EMAIL}" <<'PY'
import json
import os
import subprocess
import sys
import tempfile

dataset, email = sys.argv[1], sys.argv[2]
raw = subprocess.check_output(
    ["bq", "show", "--format=prettyjson", dataset], text=True
)
ds = json.loads(raw)
access = ds.get("access") or []
if any(
    e.get("userByEmail") == email and e.get("role") in ("READER", "WRITER", "OWNER")
    for e in access
):
    print(f"ACL ya existe: {dataset}")
    sys.exit(0)
access.append({"role": "READER", "userByEmail": email})
ds["access"] = access
fd, path = tempfile.mkstemp(suffix=".json")
try:
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        json.dump(ds, fh)
    subprocess.check_call(["bq", "update", "--source", path, dataset])
finally:
    os.remove(path)
print(f"ACL READER: {dataset} -> {email}")
PY
}

gcloud config set project "${COMPUTE_PROJECT}"

gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  artifactregistry.googleapis.com \
  bigquery.googleapis.com \
  iam.googleapis.com

if ! gcloud artifacts repositories describe "${APP}" --location="${REGION}" >/dev/null 2>&1; then
  gcloud artifacts repositories create "${APP}" \
    --repository-format=docker \
    --location="${REGION}" \
    --description="Imágenes Cloud Run de ${APP}"
fi

if ! gcloud iam service-accounts describe "${SA_EMAIL}" >/dev/null 2>&1; then
  echo "No existe la cuenta de servicio ${SA_EMAIL}" >&2
  exit 1
fi

gcloud projects add-iam-policy-binding "${COMPUTE_PROJECT}" \
  --member="serviceAccount:${SA_EMAIL}" \
  --role="roles/bigquery.jobUser" \
  --condition=None

grant_dataset_reader "${DATA_CENTRAL}:settings"

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
  echo "ACL gold: ${TENANT}"
  grant_dataset_reader "${TENANT}:gold"
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
