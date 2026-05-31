{{/* Expand the name of the chart. */}}
{{- define "atlaslens.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Fully-qualified app name. */}}
{{- define "atlaslens.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "atlaslens.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels. */}}
{{- define "atlaslens.labels" -}}
helm.sh/chart: {{ include "atlaslens.chart" . }}
app.kubernetes.io/name: {{ include "atlaslens.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Name of the Secret the backend should read from. */}}
{{- define "atlaslens.secretName" -}}
{{- if .Values.secrets.existingSecret -}}
{{- .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "atlaslens.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/* Name of the config ConfigMap. */}}
{{- define "atlaslens.configMapName" -}}
{{- printf "%s-config" (include "atlaslens.fullname" .) -}}
{{- end -}}

{{/* MongoDB service name. */}}
{{- define "atlaslens.mongoServiceName" -}}
{{- printf "%s-mongo" (include "atlaslens.fullname" .) -}}
{{- end -}}

{{/* Resolved Mongo URI: explicit override wins, else in-chart service. */}}
{{- define "atlaslens.mongoUri" -}}
{{- if .Values.config.mongoUri -}}
{{- .Values.config.mongoUri -}}
{{- else -}}
{{- printf "mongodb://%s:%v" (include "atlaslens.mongoServiceName" .) .Values.mongodb.service.port -}}
{{- end -}}
{{- end -}}
