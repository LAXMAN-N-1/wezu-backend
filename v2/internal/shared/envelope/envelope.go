package envelope

import (
	"encoding/json"
	"net/http"
)

type Meta struct {
	TraceID   string  `json:"trace_id,omitempty"`
	LatencyMS int64   `json:"latency_ms,omitempty"`
	Cached    bool    `json:"cached,omitempty"`
	Stale     bool    `json:"stale,omitempty"`
	Cursor    *string `json:"cursor,omitempty"`
}

type APIError struct {
	Code    string `json:"code"`
	Message string `json:"message"`
}

type Response struct {
	Data  any       `json:"data,omitempty"`
	Meta  Meta      `json:"meta"`
	Error *APIError `json:"error,omitempty"`
}

func OK(w http.ResponseWriter, meta Meta, data any) {
	write(w, http.StatusOK, Response{Data: data, Meta: meta})
}

func Created(w http.ResponseWriter, meta Meta, data any) {
	write(w, http.StatusCreated, Response{Data: data, Meta: meta})
}

func Fail(w http.ResponseWriter, status int, meta Meta, code, message string) {
	write(w, status, Response{Meta: meta, Error: &APIError{Code: code, Message: message}})
}

func write(w http.ResponseWriter, status int, body Response) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(body)
}
