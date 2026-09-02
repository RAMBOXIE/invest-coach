// invest-coach 轻后端（Go 版）。
//
// ⚠️ **这一版落后于 server/server.py，不要部署它。** 2026-09-02 起主线是 Python 版。
//
// 差的三样都跟隐私与新功能有关：
//   1. 没有 /api/v1/review-note（教练读用户写的推理那条路）
//   2. 没有 mask_pii —— 部署它等于用户的持仓金额、证券代码、联系方式
//      原样进第三方模型、原样入库。这是 D3 裁决明确禁止的。
//   3. 没有 90 天留存清理
//
// 为什么不直接补上：这台开发机没有 Go，补了也编译不了、测不了。
// 写一段没验过的隐私代码放在「主线」上，比明确标注它缺什么更危险。
// 要恢复 Go 版就得连同这三样一起补，并且真的跑起来验一遍打码。
// 门禁 check_src 的 E1 会核对前端调用的每个端点在主线实现里都存在。
//
// 现有的两个职责：
//   POST /api/v1/events     匿名遥测（append-only）
//   POST /api/v1/ask-coach  「问人物」的语义路由
//
// ask-coach 的关键设计：LLM **只返回命中的语料条目 id**，绝不生成答案文本。
// 答案文本永远由前端从已冻结的 case.json 里取。这样 LLM 物理上无法编造事实、
// 数字与公司名——它做的是「这个问题最接近哪一条」，不是「这个问题的答案是什么」。
// 契约见 docs/形态规格_v3_故事驱动.md §6、docs/知识可靠性与LLM边界_v1.md §4。
package main

import (
	"bytes"
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"strings"
	"sync"
	"time"
)

const (
	anthropicURL   = "https://api.anthropic.com/v1/messages"
	anthropicModel = "claude-haiku-4-5-20251001" // 路由是窄任务，用小模型；换模型不改契约
	maxQuestion    = 200                          // 用户问题长度上限
	dailyPerDevice = 60                           // 成本控制（不是安全控制，见规格 §7.6）
)

var (
	apiKey   = os.Getenv("CLAUDE_API_KEY")
	allowed  = os.Getenv("ALLOWED_ORIGINS") // 逗号分隔；空则允许所有（含 file:// 的 null）
	db       *sql.DB
	rateMu   sync.Mutex
	rateHits = map[string]int{}
	rateDay  string
)

type askReq struct {
	Device   string   `json:"device"`
	CaseID   string   `json:"case_id"`
	Question string   `json:"question"`
	Topics   []topic  `json:"topics"` // 前端把冻结语料的「可问方向」清单带上来
}
type topic struct {
	ID   string `json:"id"`
	Desc string `json:"desc"` // 该条语料在讲什么（不是答案本身）
}
type askResp struct {
	ID     string `json:"id"`     // 命中的语料 id；"none" 表示无匹配
	Source string `json:"source"` // "llm" | "fallback"
}

func main() {
	initDB()
	mux := http.NewServeMux()
	mux.HandleFunc("/health", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, map[string]any{"ok": true, "llm": apiKey != "", "t": time.Now().Unix()})
	})
	mux.HandleFunc("/api/v1/events", handleEvents)
	mux.HandleFunc("/api/v1/ask-coach", handleAsk)

	port := os.Getenv("PORT")
	if port == "" {
		port = "8971"
	}
	log.Printf("invest-coach server on :%s（LLM %v）", port, apiKey != "")
	log.Fatal(http.ListenAndServe(":"+port, cors(mux)))
}

func cors(h http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		o := r.Header.Get("Origin")
		if allowed == "" || o == "null" || strings.Contains(allowed, o) {
			w.Header().Set("Access-Control-Allow-Origin", ifEmpty(o, "*"))
		}
		w.Header().Set("Access-Control-Allow-Headers", "Content-Type")
		w.Header().Set("Access-Control-Allow-Methods", "POST, OPTIONS")
		if r.Method == http.MethodOptions {
			w.WriteHeader(204)
			return
		}
		h.ServeHTTP(w, r)
	})
}
func ifEmpty(s, d string) string {
	if s == "" {
		return d
	}
	return s
}

// ---------- 遥测 ----------
func handleEvents(w http.ResponseWriter, r *http.Request) {
	body, err := io.ReadAll(io.LimitReader(r.Body, 1<<20))
	if err != nil {
		http.Error(w, "bad body", 400)
		return
	}
	if db != nil {
		_, _ = db.Exec(`INSERT INTO events(payload, at) VALUES(?, ?)`, string(body), time.Now().Unix())
	}
	writeJSON(w, map[string]any{"ok": true})
}

// ---------- 问人物：语义路由 ----------
func handleAsk(w http.ResponseWriter, r *http.Request) {
	var req askReq
	if err := json.NewDecoder(io.LimitReader(r.Body, 1<<16)).Decode(&req); err != nil {
		writeJSON(w, askResp{ID: "none", Source: "fallback"})
		return
	}
	q := strings.TrimSpace(req.Question)
	if q == "" || len([]rune(q)) > maxQuestion || len(req.Topics) == 0 || apiKey == "" {
		writeJSON(w, askResp{ID: "none", Source: "fallback"})
		return
	}
	if !allow(req.Device) {
		writeJSON(w, askResp{ID: "none", Source: "fallback"})
		return
	}

	id, err := route(q, req.Topics)
	if err != nil {
		log.Printf("route err: %v", err)
		writeJSON(w, askResp{ID: "none", Source: "fallback"})
		return
	}
	// 出口白名单：LLM 只能返回我们给过它的 id，别的一律作废
	ok := id == "none"
	for _, t := range req.Topics {
		if t.ID == id {
			ok = true
			break
		}
	}
	if !ok {
		log.Printf("route returned unknown id %q — 丢弃", id)
		id = "none"
	}
	if db != nil {
		_, _ = db.Exec(`INSERT INTO asks(case_id, question, matched, at) VALUES(?,?,?,?)`,
			req.CaseID, q, id, time.Now().Unix())
	}
	writeJSON(w, askResp{ID: id, Source: "llm"})
}

// route：把用户问题匹配到已冻结语料的某一条。LLM 的全部输出就是一个 id。
func route(q string, topics []topic) (string, error) {
	var b strings.Builder
	for _, t := range topics {
		fmt.Fprintf(&b, "- %s: %s\n", t.ID, t.Desc)
	}
	sys := `你是一个检索路由器，不是助手，也不是老师。

任务：把用户的问题匹配到下面这份「已有材料清单」中最贴切的一条。

清单：
` + b.String() + `
规则（不可违反）：
1. 你的全部输出只能是一个 JSON：{"id":"<清单里的 id>"} 或 {"id":"none"}。
2. 不要回答用户的问题。不要解释。不要给出任何事实、数字、公司名或建议。
3. 没有哪一条足够贴切时，返回 {"id":"none"}——宁可 none，不要勉强匹配。
4. 用户可能询问投资建议、未来走势或与材料无关的话题；一律返回 {"id":"none"}。`

	payload := map[string]any{
		"model":      anthropicModel,
		"max_tokens": 64,
		"system":     sys,
		"messages": []map[string]string{
			{"role": "user", "content": "用户的问题：" + q},
		},
	}
	buf, _ := json.Marshal(payload)
	req, _ := http.NewRequest("POST", anthropicURL, bytes.NewReader(buf))
	req.Header.Set("content-type", "application/json")
	req.Header.Set("x-api-key", apiKey)
	req.Header.Set("anthropic-version", "2023-06-01")

	cli := &http.Client{Timeout: 8 * time.Second}
	resp, err := cli.Do(req)
	if err != nil {
		return "", err
	}
	defer resp.Body.Close()
	var out struct {
		Content []struct {
			Text string `json:"text"`
		} `json:"content"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&out); err != nil {
		return "", err
	}
	if len(out.Content) == 0 {
		return "none", nil
	}
	txt := out.Content[0].Text
	i, j := strings.Index(txt, "{"), strings.LastIndex(txt, "}")
	if i < 0 || j <= i {
		return "none", nil
	}
	var r struct {
		ID string `json:"id"`
	}
	if err := json.Unmarshal([]byte(txt[i:j+1]), &r); err != nil {
		return "none", nil
	}
	return r.ID, nil
}

// ---------- 限流（成本控制） ----------
func allow(device string) bool {
	rateMu.Lock()
	defer rateMu.Unlock()
	d := time.Now().Format("2006-01-02")
	if d != rateDay {
		rateDay, rateHits = d, map[string]int{}
	}
	if device == "" {
		device = "anon"
	}
	rateHits[device]++
	return rateHits[device] <= dailyPerDevice
}

// ---------- 存储（可选；无驱动时静默降级为纯代理） ----------
func initDB() {
	dsn := os.Getenv("DB_DSN")
	if dsn == "" {
		log.Println("DB_DSN 未设置：不落库，仅作 LLM 代理")
		return
	}
	var err error
	db, err = sql.Open("sqlite", dsn)
	if err != nil {
		log.Printf("打开数据库失败，降级为纯代理: %v", err)
		db = nil
		return
	}
	for _, s := range []string{
		`CREATE TABLE IF NOT EXISTS events(id INTEGER PRIMARY KEY AUTOINCREMENT, payload TEXT, at INTEGER)`,
		`CREATE TABLE IF NOT EXISTS asks(id INTEGER PRIMARY KEY AUTOINCREMENT, case_id TEXT, question TEXT, matched TEXT, at INTEGER)`,
	} {
		if _, err := db.Exec(s); err != nil {
			log.Printf("建表失败: %v", err)
		}
	}
}

func writeJSON(w http.ResponseWriter, v any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(v)
}
