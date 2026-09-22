#!/usr/bin/env bash
# One-shot: install ADO Pre-Flight Operator on ocp-dev WITH icon
# Serves fixed catalog from ConfigMap (cluster image registry is Removed).
set -euo pipefail

NS=openshift-marketplace
OPNS=openshift-operators
ICON_PNG="${ICON_PNG:-/home/chelliot/openshift/git/github-ado/ado-preflight-ui/ado-sample-icon.png}"
CATALOG_SRC="${CATALOG_SRC:-/home/chelliot/openshift/git/github-ado/ado/.tmp-for-lance/catalog-with-icon.yaml}"

if [[ ! -f "$CATALOG_SRC" ]]; then
  echo "ERROR: missing $CATALOG_SRC — run the prepare steps first (or ask agent to regenerate)."
  exit 1
fi
if [[ ! -f "$ICON_PNG" ]]; then
  echo "ERROR: missing icon $ICON_PNG"
  exit 1
fi

echo "== cleanup old operator bits =="
oc delete adopreflightui --all -A --ignore-not-found 2>/dev/null || true
oc delete subscription ado-preflight-operator -n "$OPNS" --ignore-not-found 2>/dev/null || true
oc delete catalogsource ado-preflight-operator-catalog -n "$NS" --ignore-not-found 2>/dev/null || true
oc delete deploy,svc,cm -n "$NS" -l app=ado-preflight-operator-catalog --ignore-not-found 2>/dev/null || true
# orphaned CSVs from AllNamespaces install
if command -v jq >/dev/null; then
  oc get csv -A -o json 2>/dev/null \
    | jq -r '.items[] | select(.metadata.name=="ado-preflight-operator.v0.0.2") | "\(.metadata.namespace) \(.metadata.name)"' \
    | while read -r ns name; do oc delete csv "$name" -n "$ns" --ignore-not-found; done || true
fi
oc delete operator ado-preflight-operator.openshift-operators --ignore-not-found 2>/dev/null || true
oc delete crd adopreflightuis.preflight.ado.io --ignore-not-found 2>/dev/null || true

echo "== create catalog ConfigMap + Deployment (icon baked in) =="
oc apply -f - <<'EOF'
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: ado-preflight-operator-catalog-grpc
  namespace: openshift-marketplace
  labels:
    app: ado-preflight-operator-catalog
spec:
  podSelector:
    matchLabels:
      app: ado-preflight-operator-catalog
  policyTypes:
    - Ingress
  ingress:
    - ports:
        - protocol: TCP
          port: 50051
EOF

oc create configmap ado-preflight-operator-catalog \
  -n "$NS" \
  --from-file=catalog.yaml="$CATALOG_SRC" \
  -o yaml --dry-run=client \
  | oc label --local -f - app=ado-preflight-operator-catalog -o yaml \
  | oc apply -f -

oc apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: ado-preflight-operator-catalog
  namespace: ${NS}
  labels:
    app: ado-preflight-operator-catalog
spec:
  replicas: 1
  selector:
    matchLabels:
      app: ado-preflight-operator-catalog
  template:
    metadata:
      labels:
        app: ado-preflight-operator-catalog
    spec:
      securityContext:
        runAsNonRoot: true
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: registry
          # same base as the Quay catalog; we override /configs with our ConfigMap
          image: quay.io/rh-ee-lcorder/ado-preflight-operator-catalog:v0.0.2
          imagePullPolicy: IfNotPresent
          args:
            - serve
            - /configs
            - --cache-enforce-integrity=false
          ports:
            - name: grpc
              containerPort: 50051
          securityContext:
            allowPrivilegeEscalation: false
            capabilities:
              drop: ["ALL"]
          volumeMounts:
            - name: configs
              mountPath: /configs/ado-preflight-operator/catalog.yaml
              subPath: catalog.yaml
          readinessProbe:
            exec:
              command: ["grpc_health_probe", "-addr=:50051"]
            initialDelaySeconds: 5
            periodSeconds: 10
            failureThreshold: 6
          livenessProbe:
            exec:
              command: ["grpc_health_probe", "-addr=:50051"]
            initialDelaySeconds: 15
            periodSeconds: 20
            failureThreshold: 6
      volumes:
        - name: configs
          configMap:
            name: ado-preflight-operator-catalog
---
apiVersion: v1
kind: Service
metadata:
  name: ado-preflight-operator-catalog
  namespace: ${NS}
  labels:
    app: ado-preflight-operator-catalog
spec:
  selector:
    app: ado-preflight-operator-catalog
  ports:
    - name: grpc
      port: 50051
      targetPort: grpc
---
apiVersion: operators.coreos.com/v1alpha1
kind: CatalogSource
metadata:
  name: ado-preflight-operator-catalog
  namespace: ${NS}
spec:
  sourceType: grpc
  address: ado-preflight-operator-catalog.${NS}.svc:50051
  displayName: ADO Pre-Flight Operator
  publisher: Automation Development Office
  updateStrategy:
    registryPoll:
      interval: 10m
EOF

echo "== wait for catalog pod =="
oc rollout status deployment/ado-preflight-operator-catalog -n "$NS" --timeout=180s
oc wait --for=condition=Ready pod -l app=ado-preflight-operator-catalog -n "$NS" --timeout=180s

echo "== wait for PackageManifest =="
for i in $(seq 1 36); do
  if oc get packagemanifest ado-preflight-operator -n "$NS" >/dev/null 2>&1; then
    echo "PackageManifest ready"
    break
  fi
  sleep 5
done
oc get packagemanifest ado-preflight-operator -n "$NS" -o yaml | grep -A2 'mediatype: image/png' | head -5 || true

echo "== subscribe (install operator) =="
oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: ado-preflight-operator
  namespace: ${OPNS}
spec:
  channel: alpha
  installPlanApproval: Automatic
  name: ado-preflight-operator
  source: ado-preflight-operator-catalog
  sourceNamespace: ${NS}
EOF

echo "== wait for CSV Succeeded =="
for i in $(seq 1 60); do
  PHASE=$(oc get csv -n "$OPNS" -o jsonpath='{range .items[?(@.metadata.name=="ado-preflight-operator.v0.0.2")]}{.status.phase}{end}' 2>/dev/null || true)
  echo "CSV phase=$PHASE"
  [[ "$PHASE" == "Succeeded" ]] && break
  sleep 5
done

echo
echo "DONE. OperatorHub → search ADO Pre (hard-refresh browser)."
echo "Optional UI instance:"
echo "  oc apply -f - <<'CR'"
echo "  apiVersion: preflight.ado.io/v1alpha1"
echo "  kind: AdoPreflightUI"
echo "  metadata:"
echo "    name: preflight"
echo "    namespace: ado-portal"
echo "  spec:"
echo "    image:"
echo "      repository: ghcr.io/automation-development-office/ado-preflight-ui"
echo "      tag: latest"
echo "    terminal:"
echo "      enabled: true"
echo "    workspace:"
echo "      storageSize: 5Gi"
echo "    route:"
echo "      enabled: true"
echo "  CR"
