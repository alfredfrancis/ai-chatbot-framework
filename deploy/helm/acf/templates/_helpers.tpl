{{- define "acf.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else if contains .Chart.Name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "acf.selectorLabels" -}}
app.kubernetes.io/name: {{ .Chart.Name }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "acf.labels" -}}
{{ include "acf.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "acf.image" -}}
{{ .Values.image.repository }}:{{ .Values.image.tag | default .Chart.AppVersion }}
{{- end -}}

{{- define "acf.sandboxImage" -}}
{{ .Values.sandbox.image | default (printf "alfredfrancis/acf-sandbox:%s" .Chart.AppVersion) }}
{{- end -}}

{{- define "acf.serviceAccount" -}}
{{ include "acf.fullname" . }}
{{- end -}}

{{- define "acf.dataClaim" -}}
{{ .Values.persistence.existingClaim | default (printf "%s-data" (include "acf.fullname" .)) }}
{{- end -}}

{{- define "acf.publicUrl" -}}
{{- if .Values.publicUrl -}}
{{ .Values.publicUrl | trimSuffix "/" }}
{{- else if and .Values.ingress.enabled .Values.ingress.host -}}
https://{{ .Values.ingress.host }}
{{- end -}}
{{- end -}}

{{- define "acf.redisGiven" -}}
{{- if or .Values.redis.url .Values.redis.existingSecret.name }}true{{ end -}}
{{- end -}}

{{/*
The values that go into the chart's own Secret, as a YAML map (empty when everything comes from Secrets the
operator manages).
*/}}
{{- define "acf.secretData" -}}
{{- if not .Values.existingSecret }}
ACF_SECRET_KEY: {{ .Values.secretKey | quote }}
{{- if .Values.llm.apiKey }}
ACF_LLM_API_KEY: {{ .Values.llm.apiKey | quote }}
{{- end }}
{{- end }}
{{- if .Values.database.url }}
ACF_DB_URL: {{ .Values.database.url | quote }}
{{- end }}
{{- if .Values.redis.url }}
ACF_REDIS_URL: {{ .Values.redis.url | quote }}
{{- end }}
{{- end -}}

{{/*
Where each secret variable comes from: {name: {secret, key, optional}}. Pods get secrets only as secretKeyRef,
because the app's ServiceAccount can read every pod spec in the namespace.
*/}}
{{- define "acf.secretRefs" -}}
{{- $own := include "acf.fullname" . -}}
{{- $refs := dict -}}
{{- if .Values.existingSecret -}}
{{- $_ := set $refs "ACF_SECRET_KEY" (dict "secret" .Values.existingSecret "key" "ACF_SECRET_KEY") -}}
{{- $_ := set $refs "ACF_LLM_API_KEY" (dict "secret" .Values.existingSecret "key" "ACF_LLM_API_KEY" "optional" true) -}}
{{- else -}}
{{- $_ := set $refs "ACF_SECRET_KEY" (dict "secret" $own "key" "ACF_SECRET_KEY") -}}
{{- if .Values.llm.apiKey -}}
{{- $_ := set $refs "ACF_LLM_API_KEY" (dict "secret" $own "key" "ACF_LLM_API_KEY") -}}
{{- end -}}
{{- end -}}
{{- if .Values.database.existingSecret.name -}}
{{- $_ := set $refs "ACF_DB_URL" (dict "secret" .Values.database.existingSecret.name "key" .Values.database.existingSecret.key) -}}
{{- else if .Values.database.url -}}
{{- $_ := set $refs "ACF_DB_URL" (dict "secret" $own "key" "ACF_DB_URL") -}}
{{- end -}}
{{- if .Values.redis.existingSecret.name -}}
{{- $_ := set $refs "ACF_REDIS_URL" (dict "secret" .Values.redis.existingSecret.name "key" .Values.redis.existingSecret.key) -}}
{{- else if .Values.redis.url -}}
{{- $_ := set $refs "ACF_REDIS_URL" (dict "secret" $own "key" "ACF_REDIS_URL") -}}
{{- end -}}
{{- toYaml $refs -}}
{{- end -}}

{{/* EnvVar entries for the named secret variables that are configured. */}}
{{- define "acf.secretEnv" -}}
{{- $refs := include "acf.secretRefs" .root | fromYaml -}}
{{- range $name := .names }}
{{- with get $refs $name }}
- name: {{ $name }}
  valueFrom:
    secretKeyRef:
      name: {{ .secret }}
      key: {{ .key }}
      {{- if .optional }}
      optional: true
      {{- end }}
{{- end }}
{{- end }}
{{- end -}}

{{/* Pod Security `restricted`, for every container of the chart. */}}
{{- define "acf.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
fsGroup: 10001
fsGroupChangePolicy: OnRootMismatch
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "acf.containerSecurityContext" -}}
runAsNonRoot: true
runAsUser: 10001
runAsGroup: 10001
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* Settings the chart sets itself, so `env` can't change them. */}}
{{- define "acf.managedEnv" -}}
{{- list "ACF_SANDBOX" "ACF_K8S_NAMESPACE" "ACF_K8S_DATA_CLAIM" "ACF_DATA_DIR" "ACF_MIGRATE_ON_START" "ACF_PUBLIC_URL" "ACF_COOKIE_SECURE" "ACF_SANDBOX_IMAGE" "ACF_SANDBOX_RUNTIME" "ACF_SANDBOX_MEMORY" "ACF_SANDBOX_CPUS" "ACF_SANDBOX_IDLE_MINUTES" "ACF_SHUTDOWN_GRACE" "ACF_LOG_FORMAT" "ACF_LLM_PROVIDER" "ACF_LLM_MODEL" "ACF_LLM_BASE_URL" "ACF_SECRET_KEY" "ACF_LLM_API_KEY" "ACF_DB_URL" "ACF_REDIS_URL" "ACF_ADMIN_PASSWORD" "HOME" | toYaml -}}
{{- end -}}

{{/* Every check that must hold before anything is installed. */}}
{{- define "acf.validate" -}}
{{- $v := .Values -}}
{{- if $v.existingSecret -}}
{{- if or $v.secretKey $v.llm.apiKey -}}
{{- fail "existingSecret is set: put ACF_SECRET_KEY and ACF_LLM_API_KEY in that Secret, and leave secretKey and llm.apiKey empty" -}}
{{- end -}}
{{- else if lt (len $v.secretKey) 32 -}}
{{- fail "Set secretKey (at least 32 characters, e.g. `openssl rand -base64 48`), or existingSecret: a Secret with the key ACF_SECRET_KEY" -}}
{{- end -}}
{{- if and $v.database.url $v.database.existingSecret.name -}}
{{- fail "Set database.url or database.existingSecret.name, not both" -}}
{{- end -}}
{{- if not (or $v.database.url $v.database.existingSecret.name) -}}
{{- fail "Set database.url (postgresql://...) or database.existingSecret.name: the app needs PostgreSQL" -}}
{{- end -}}
{{- if and $v.redis.url $v.redis.existingSecret.name -}}
{{- fail "Set redis.url or redis.existingSecret.name, not both" -}}
{{- end -}}
{{- $scales := or (gt (int $v.replicas) 1) (and $v.autoscaling.enabled (gt (int $v.autoscaling.maxReplicas) 1)) -}}
{{- if and $scales (not (include "acf.redisGiven" .)) -}}
{{- fail "More than one app replica needs Redis, which shares run state between them: set redis.url or redis.existingSecret.name, or set replicas to 1" -}}
{{- end -}}
{{- if and $v.autoscaling.enabled (not (dig "requests" "cpu" "" $v.resources)) -}}
{{- fail "autoscaling scales on CPU: set resources.requests.cpu" -}}
{{- end -}}
{{- if not (include "acf.publicUrl" .) -}}
{{- fail "Set publicUrl (the web app's address, e.g. https://acf.example.com), or enable the Ingress with a host" -}}
{{- end -}}
{{- if not (regexMatch "^[A-Za-z0-9][A-Za-z0-9./:@_-]*$" (include "acf.sandboxImage" .)) -}}
{{- fail "sandbox.image must be an image reference (letters, digits and . / : @ _ -)" -}}
{{- end -}}
{{- if not (regexMatch "^[a-z0-9.-]*$" $v.sandbox.runtimeClass) -}}
{{- fail "sandbox.runtimeClass must be a RuntimeClass name, or empty" -}}
{{- end -}}
{{- range $name, $_ := $v.otel -}}
{{- if not (hasPrefix "OTEL_" $name) -}}
{{- fail (printf "otel: %s doesn't start with OTEL_; put other settings in env" $name) -}}
{{- end -}}
{{- end -}}
{{- $managed := include "acf.managedEnv" . | fromYamlArray -}}
{{- range $name, $_ := $v.env -}}
{{- if has $name $managed -}}
{{- fail (printf "env: the chart sets %s itself (see values.yaml); secrets go in extraEnv as a secretKeyRef" $name) -}}
{{- end -}}
{{- end -}}
{{- if $v.guardrails.requireRestrictedNamespace -}}
{{- $want := (include "acf.guardrail" (dict "root" . "file" "namespace") | fromYaml).metadata.labels -}}
{{- with lookup "v1" "Namespace" "" .Release.Namespace -}}
{{- $have := .metadata.labels | default dict -}}
{{- $missing := list -}}
{{- range $k, $val := $want -}}
{{- if ne (get $have $k) $val -}}
{{- $missing = append $missing (printf "%s=%s" $k $val) -}}
{{- end -}}
{{- end -}}
{{- if $missing -}}
{{- fail (printf "The namespace %s needs Pod Security `restricted`: kubectl label namespace %s --overwrite %s (or set guardrails.requireRestrictedNamespace=false if a cluster-wide admission configuration enforces it)" .metadata.name .metadata.name (join " " $missing)) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
One file of deploy/kubernetes/ (guardrails/ links to it), with its ${...} placeholders filled in as `envsubst`
would. A placeholder this chart doesn't know fails the render.
*/}}
{{- define "acf.guardrail" -}}
{{- $root := .root -}}
{{- $text := $root.Files.Get (printf "guardrails/%s.yaml" .file) -}}
{{- if not $text -}}
{{- fail (printf "guardrails/%s.yaml is missing or empty" .file) -}}
{{- end -}}
{{- $values := dict
  "NAMESPACE" $root.Release.Namespace
  "SERVICE_ACCOUNT" (include "acf.serviceAccount" $root)
  "IMAGE" (include "acf.sandboxImage" $root)
  "DATA_CLAIM" (include "acf.dataClaim" $root)
  "RUNTIME_CLASS" $root.Values.sandbox.runtimeClass -}}
{{- range $k, $v := $values -}}
{{- $text = replace (printf "${%s}" $k) $v $text -}}
{{- end -}}
{{- with regexFind "\\$\\{[A-Za-z_]+\\}" $text -}}
{{- fail (printf "guardrails/%s.yaml has the placeholder %s, which the chart doesn't fill in" $.file .) -}}
{{- end -}}
{{- $text -}}
{{- end -}}
