(function () {
  "use strict";

  const $ = (selector, parent = document) => parent.querySelector(selector);
  const $$ = (selector, parent = document) => [...parent.querySelectorAll(selector)];
  const modes = {
    knowledge: "정보 · 지식",
    product: "제품 · 브랜드",
    highlights: "영상 하이라이트",
  };
  const modeEnglish = {
    knowledge: "TIP & INSIGHT",
    product: "PRODUCT & BRAND",
    highlights: "CLIP & HIGHLIGHT",
  };
  const deliveries = {
    export: "파일로 내보내기",
    approval: "확인 후 업로드",
    auto: "자동 업로드",
  };
  const statuses = {
    queued: "대기 중", draft: "초안", generating: "대본 생성 중",
    rendering: "영상 편집 중", ready: "제작 완료", approved: "승인됨",
    scheduled: "예약됨", publishing: "게시 중", published: "게시 완료", failed: "오류",
  };
  const activeStatuses = new Set(["queued", "generating", "rendering", "publishing"]);

  function icon(name) {
    const namespace = "http://www.w3.org/2000/svg";
    const element = document.createElementNS(namespace, "svg");
    const use = document.createElementNS(namespace, "use");
    use.setAttribute("href", `#i-${name}`);
    element.append(use);
    return element;
  }

  function node(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  async function api(path, options = {}) {
    const { raw = false, ...request } = options;
    const headers = raw ? {} : { "Content-Type": "application/json" };
    const response = await fetch(path, {
      ...request,
      headers: { ...headers, ...request.headers },
      body: request.body === undefined ? undefined : raw ? request.body : JSON.stringify(request.body),
    });
    const text = await response.text();
    let result;
    try {
      result = text ? JSON.parse(text) : {};
    } catch {
      throw new Error(`서버 응답을 읽지 못했습니다 (${response.status}).`);
    }
    if (!response.ok) {
      throw new Error(result.error || `요청을 처리하지 못했습니다 (${response.status}).`);
    }
    return result;
  }

  function dateLabel(value, withTime = false) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    const format = withTime
      ? { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }
      : { year: "numeric", month: "2-digit", day: "2-digit" };
    return date.toLocaleString("ko-KR", format);
  }

  function localDatetime(value) {
    if (!value) return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function jobAssetUrl(value) {
    if (!value) return "";
    if (typeof value === "string") return value;
    if (typeof value === "object") return value.url || value.path || "";
    return "";
  }

  window.ReelCore = Object.freeze({
    $, $$, modes, modeEnglish, deliveries, statuses, activeStatuses,
    icon, node, api, dateLabel, localDatetime, jobAssetUrl,
  });
}());
