# Run Cutly on Kubernetes

**Kubernetes** option for deploying **Cutly** (Flask + Postgres + Redis). It contains:

- Kubernetes prerequisites
- Image build & registry push
- Namespaces, ConfigMap & Secret
- Postgres StatefulSet (PVC)
- Redis Deployment
- Web Deployment + Service + Ingress

> This is intended as an *add-on* to your existing Docker / docker-compose setup. Keep the original `docker-compose` files for local dev; use the manifests below for cluster deployments.

---

## 1. Prerequisites

- A Kubernetes cluster (minikube / k3s / GKE / EKS / AKS, etc.)
- `kubectl` configured for the cluster
- A container registry (Docker Hub, GitHub Container Registry, GCR, ECR, etc.)

---

## 2. Build & push the image

Build and push your Flask image to a registry accessible by the cluster:

```bash
# from repo root
docker build -t <docker hub username>/cutly:v1 .

docker push <docker hub username>/cutly:v1
```

---

## 3. Create a namespace

```bash
kubectl create namespace cutly
```

---

## 4. Secrets & ConfigMap

Create a `ConfigMap` for non-sensitive configs and a `Secret` for passwords, session secret, DB creds.

`k8s/config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: cutly-config
  namespace: cutly
data:
  WEB_PORT: "5000"
  # other non-sensitive values
```

`k8s/secret.yaml` (store sensitive values base64 or use kubectl create secret):

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: cutly-secrets
  namespace: cutly
type: Opaque
stringData:
  DB_USER: cutly
  DB_PASSWORD: your_db_password_here
  DB_NAME: cutlydb
  SESSION_SECRET: "supersecret"
  POSTGRES_PASSWORD: "postgres-password"
```

You can also create via command line (avoids storing secrets in repo):

```bash
kubectl -n cutly create secret generic cutly-secrets \
  --from-literal=DB_USER=cutly \
  --from-literal=DB_PASSWORD=your_db_password_here \
  --from-literal=DB_NAME=cutlydb \
  --from-literal=SESSION_SECRET=supersecret \
  --from-literal=POSTGRES_PASSWORD=postgres-password
```

---

## 5. Postgres: StatefulSet + PVC

Use a StatefulSet for Postgres to keep stable storage.

`k8s/postgres.yaml`:

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: pgdata
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 5Gi
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres
spec:
  selector:
    matchLabels: { app: postgres }
  template:
    metadata:
      labels: { app: postgres }
    spec:
      containers:
        - name: postgres
          image: postgres:16
          env:
            - name: POSTGRES_DB
              valueFrom: { configMapKeyRef: { name: cutly-config, key: DB_NAME } }
            - name: POSTGRES_USER
              valueFrom: { configMapKeyRef: { name: cutly-config, key: DB_USER } }
            - name: POSTGRES_PASSWORD
              valueFrom: { secretKeyRef: { name: cutly-secrets, key: DB_PASSWORD } }
          ports: [{ containerPort: 5432 }]
          volumeMounts:
            - name: data
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: data
          persistentVolumeClaim:
            claimName: pgdata
---
apiVersion: v1
kind: Service
metadata:
  name: postgres
spec:
  selector: { app: postgres }
  ports:
    - port: 5432
      targetPort: 5432
```

Adjust storage size and replication to match your environment.

---

## 6. Redis: Deployment

`k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: redis
spec:
  selector:
    matchLabels: { app: redis }
  template:
    metadata:
      labels: { app: redis }
    spec:
      containers:
        - name: redis
          image: redis:7
          args: ["--appendonly", "yes"]
          ports: [{ containerPort: 6379 }]
---
apiVersion: v1
kind: Service
metadata:
  name: redis
spec:
  selector: { app: redis }
  ports:
    - port: 6379
      targetPort: 6379

```

---

## 7. Web Deployment, Service:

`k8s/deployment.yaml`:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: cutly
spec:
  replicas: 2
  selector:
    matchLabels:
      app: cutly
  template:
    metadata:
      labels:
        app: cutly
    spec:
      containers:
        - name: web
          image: cosmic09/cutly:v1
          ports:
            - containerPort: 5000
          envFrom:
            - configMapRef:
                name: cutly-config
            - secretRef:
                name: cutly-secrets
          readinessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 5
            periodSeconds: 5
          livenessProbe:
            httpGet:
              path: /healthz
              port: 5000
            initialDelaySeconds: 20
            periodSeconds: 10
          resources:
            requests:
              cpu: "100m"
              memory: "256Mi"
            limits:
              cpu: "500m"
              memory: "512Mi"

```

### Service

`k8s/service.yaml`:

```yaml
apiVersion: v1
kind: Service
metadata:
  name: cutly-svc
spec:
  selector:
    app: cutly
  ports:
    - name: http
      port: 80
      targetPort: 5000
  type: ClusterIP
```
---

## 8. Apply manifests

```bash
kubectl apply -n cutly -f k8s/config.yaml
kubectl apply -n cutly -f k8s/secrets.yaml
kubectl apply -n cutly -f k8s/postgres.yaml
kubectl apply -n cutly -f k8s/redis.yaml
kubectl apply -n cutly -f k8s/deployment.yaml
kubectl apply -n cutly -f k8s/service.yaml
```

Check pods & services:

```bash
kubectl -n cutly get pods
kubectl -n cutly get svc
kubectl -n cutly get sts
```

To port-forward the web service locally:

```bash
kubectl -n cutly port-forward svc/cutly-service 8080:80
# open http://localhost:8080
```

---

### 9. Stop Services:
Scale replicas down to zero:
```bash
kubectl -n cutly scale <pod-name> --replicas=0
```


## 10. Folder layout

```
Cutly/
└── k8s/
    ├── configmap.yaml
    ├── secret.yaml
    ├── postgres.yaml
    ├── redis.yaml
    ├── deployment.yaml
    └── service.yaml
```

