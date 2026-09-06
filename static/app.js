"use strict";

const {
  $, $$, modes, modeEnglish, deliveries, statuses, activeStatuses,
  icon, node, api, dateLabel, localDatetime, jobAssetUrl,
} = window.ReelCore;

const state = {
  jobs: [], settings: {}, capabilities: {}, automations: [],
  selectedId: null, job: null, assets: [], script: null,
  formDirty: false, scriptDirty: false, busy: false, uploading: 0,
  view: "studio", connected: false, polling: false, initialized: false,
};

function toast(message,error=false){const el=node("div",`toast${error?" error":""}`);el.append(icon(error?"close":"check"),node("span","",message));const close=node("button");close.type="button";close.setAttribute("aria-label","알림 닫기");close.append(icon("close"));close.onclick=()=>el.remove();el.append(close);$("#toast-region").append(el);setTimeout(()=>el.remove(),error?12000:5000);}

function setValue(selector,value){$(selector).value=value??"";}
function setChoice(name,value){const selected=$(`input[name="${name}"][value="${value}"]`);if(selected)selected.checked=true;}
function currentMode(){return $('input[name="mode"]:checked').value;}
function currentDelivery(){return $('input[name="delivery"]:checked').value;}
function statusPill(job) {
  const awaitingApproval = job.status === "ready" && job.delivery === "approval";
  const className = `status-pill ${job.status}${activeStatuses.has(job.status) ? " active" : ""}`;
  return node("span", className, awaitingApproval ? "승인 대기" : statuses[job.status] || job.status);
}

function updateJob(job){if(!job?.id)return;const index=state.jobs.findIndex(item=>item.id===job.id);if(index<0)state.jobs.unshift(job);else state.jobs[index]=job;if(state.selectedId===job.id)state.job=job;renderJobs();}

const viewNames = {studio:"제작 스튜디오",jobs:"콘텐츠 보관함",automations:"자동화 스케줄",setup:"초기 설정 가이드"};
function showView(view){
  if(!Object.hasOwn(viewNames,view))return;
  state.view=view;
  $$('.view').forEach(el=>{el.hidden=el.id!==`view-${view}`;el.classList.toggle("active",!el.hidden);});
  $$('[data-view]').forEach(el=>{
    el.classList.toggle("active",el.dataset.view===view);
    if(el.dataset.view===view)el.setAttribute("aria-current","page");else el.removeAttribute("aria-current");
  });
  $("#page-name").textContent=viewNames[view];
  history.replaceState(null,"",`#${view}`);
  if(view==="jobs")renderLibrary();
  if(view==="automations")renderAutomations();
  if(view==="setup")updateSetup();
  window.scrollTo({top:0,behavior:"smooth"});
}

function updateSetup(){window.ReelSetup?.update(state);}

function openSetupSettings(section){
  openSettings();
  const selector={openai:"#openai-key",tts:"#tts-provider",instagram:"#instagram-login"}[section]||"#openai-key";
  requestAnimationFrame(()=>{
    const input=$(selector);
    input.scrollIntoView({block:"center"});
    input.focus({preventScroll:true});
  });
}
function newProject(){state.selectedId=null;state.job=null;state.assets=[];state.script=null;state.formDirty=false;state.scriptDirty=false;$("#project-form").reset();$("#script-panel").hidden=true;$("#job-status-panel").hidden=true;renderAssets();renderSelection();renderPreview();renderJobs();updateActions();showView("studio");$("#topic").focus();}

function collectScript(){if(!state.script)return null;return {...state.script,title:$("#script-title").value.trim(),hook:$("#script-hook").value.trim(),scenes:$$('.scene-card',$("#scene-list")).map(el=>({text:$('.scene-text',el).value.trim(),narration:$('.scene-narration',el).value.trim(),duration:Number($('.scene-duration',el).value)||5})),caption:$("#script-caption").value.trim(),hashtags:$("#script-hashtags").value.split(/[\s,，]+/).map(tag=>tag.trim()).filter(Boolean).map(tag=>tag.startsWith("#")?tag:`#${tag}`)};}
function collectForm(includeScript=true){const scheduled=$("#scheduled-at").value;const data={title:$("#topic").value.trim(),topic:$("#topic").value.trim(),mode:currentMode(),delivery:currentDelivery(),source_notes:$("#source-notes").value.trim(),duration:Number($("#duration").value),tone:$("#tone").value,audience:$("#audience").value.trim(),brand:$("#brand").value.trim(),cta:$("#cta").value.trim(),assets:state.assets,clip_start:$("#clip-start").value!==""?Number($("#clip-start").value):null,clip_end:$("#clip-end").value?Number($("#clip-end").value):null,scheduled_at:scheduled&&currentDelivery()!=="export"?new Date(scheduled).toISOString():null,auto_publish:currentDelivery()==="auto"};if(includeScript&&state.script)data.script=collectScript();return data;}
function validateProject(){if(!$("#project-form").reportValidity())return false;if(state.uploading){toast("파일 업로드가 끝나면 제작을 시작할 수 있습니다.",true);return false;}if(currentMode()==="highlights"&&!state.assets.some(asset=>asset.kind==="video")){toast("하이라이트 제작에는 원본 동영상 파일을 추가하세요.",true);$("#upload-zone").scrollIntoView({behavior:"smooth",block:"center"});return false;}const start=Number($("#clip-start").value)||0;const end=$("#clip-end").value?Number($("#clip-end").value):null;if(currentMode()==="highlights"&&end!==null&&end<=start){toast("종료 지점은 시작 지점보다 뒤여야 합니다.",true);$("#clip-end").focus();return false;}return true;}
async function saveProject({quiet=false,validate=true}={}){if(validate&&!validateProject())return null;const data=collectForm();let job;if(state.selectedId&&["draft","ready","failed"].includes(state.job?.status)){job=await api(`/api/jobs/${state.selectedId}`,{method:"PATCH",body:data});}else if(state.selectedId&&activeStatuses.has(state.job?.status)){throw new Error("현재 제작이 끝난 후 수정할 수 있습니다.");}else{job=await api("/api/jobs",{method:"POST",body:data});state.selectedId=job.id;}state.formDirty=false;state.scriptDirty=false;updateJob(job);renderCurrentJob();if(!quiet)toast("프로젝트를 저장했습니다.");return job;}
async function perform(action){if(state.busy)return;state.busy=true;updateActions();try{const job=await saveProject({quiet:true});if(!job)return;const result=await api(`/api/jobs/${job.id}/${action}`,{method:"POST",body:{}});updateJob(result);renderCurrentJob();toast(action==="generate"?"대본 생성을 시작했습니다.":action==="render"?"저장한 대본으로 영상 편집을 시작했습니다.":"릴스 제작을 시작했습니다.");}catch(error){toast(error.message,true);}finally{state.busy=false;updateActions();}}
async function jobAction(action){if(!state.selectedId||state.busy)return;state.busy=true;updateActions();try{const result=await api(`/api/jobs/${state.selectedId}/${action}`,{method:"POST",body:{}});updateJob(result);renderCurrentJob();toast({approve:"승인했습니다. 설정된 시각에 게시합니다.",publish:"인스타그램 게시를 시작했습니다.",retry:"작업을 다시 시작했습니다."}[action]||"작업을 시작했습니다.");}catch(error){toast(error.message,true);}finally{state.busy=false;updateActions();}}
function loadJob(job){state.selectedId=job.id;state.job=job;state.assets=[...(job.assets||[])];state.script=job.script||null;state.formDirty=false;state.scriptDirty=false;setValue("#topic",job.topic||job.title);setValue("#source-notes",job.source_notes);setValue("#duration",job.duration||30);if(!$("#duration").value){const option=node("option","",`${job.duration}초`);option.value=job.duration;$("#duration").append(option);setValue("#duration",job.duration);}setValue("#tone",job.tone||"친근하고 명확하게");if(!$("#tone").value){const option=node("option","",job.tone);option.value=job.tone;$("#tone").append(option);setValue("#tone",job.tone);}setValue("#audience",job.audience);setValue("#brand",job.brand);setValue("#cta",job.cta);setValue("#clip-start",job.clip_start??"");setValue("#clip-end",job.clip_end);setValue("#scheduled-at",localDatetime(job.scheduled_at));setChoice("mode",job.mode||"knowledge");setChoice("delivery",job.delivery||"export");renderSelection();renderAssets();renderScript();renderCurrentJob();renderJobs();showView("studio");}
async function openJob(id){try{const job=await api(`/api/jobs/${id}`);updateJob(job);loadJob(job);}catch(error){toast(error.message,true);}}

function renderSelection(){const mode=currentMode(),delivery=currentDelivery();$("#highlight-fields").hidden=mode!=="highlights";$("#asset-hint").textContent=mode==="highlights"?"원본 동영상 필수":"선택 · 없으면 타이포그래피 영상";$("#schedule-field").hidden=delivery==="export";$("#delivery-notice").textContent=delivery==="export"?"영상, 자막, 대본, 캡션을 파일로 받아 자유롭게 활용하세요.":delivery==="approval"?"완성된 영상을 확인하고 ‘승인 후 게시’를 누르면 업로드합니다.":"이 모드를 실행하면 완성된 영상이 연결한 인스타그램 계정에 자동 게시됩니다.";renderPreview();}
function renderAssets(){const list=$("#asset-list");list.replaceChildren();state.assets.forEach((asset,index)=>{const row=node("div","asset-item");row.append(icon(asset.kind==="video"?"film":"grid"));const link=node("a","",asset.name||`소스 ${index+1}`);link.href=asset.url||"#";link.target="_blank";link.rel="noopener";row.append(link,node("small","",asset.kind==="video"?"VIDEO":"IMAGE"));const remove=node("button");remove.type="button";remove.setAttribute("aria-label",`${asset.name} 제거`);remove.append(icon("close"));remove.onclick=()=>{state.assets.splice(index,1);state.formDirty=true;renderAssets();};row.append(remove);list.append(row);});}
async function uploadFiles(files){const accepted=[...files].filter(file=>file.type.startsWith("image/")||file.type.startsWith("video/")||/\.(mp4|mov|webm|mkv|avi|m4v|png|jpe?g|webp|gif|bmp)$/i.test(file.name));if(!accepted.length){toast("이미지 또는 동영상 파일을 선택하세요.",true);return;}state.uploading+=accepted.length;updateActions();for(const file of accepted){$("#upload-status").textContent=`업로드 중 · ${file.name} (${(file.size/1024/1024).toFixed(1)} MB)`;try{const asset=await api(`/api/assets?name=${encodeURIComponent(file.name)}`,{method:"POST",raw:true,body:file,headers:{"Content-Type":file.type||"application/octet-stream"}});state.assets.push(asset);state.formDirty=true;renderAssets();}catch(error){toast(`${file.name}: ${error.message}`,true);}finally{state.uploading--;}}$("#upload-status").textContent=state.uploading?"파일 업로드 중…":`${state.assets.length}개 소스 준비 완료`;$("#asset-upload").value="";updateActions();}

function renderPreview(){const videoUrl=jobAssetUrl(state.job?.artifacts?.video);const video=$("#video-preview");if(videoUrl){if(video.getAttribute("src")!==videoUrl)video.src=videoUrl;video.hidden=false;$("#storyboard").hidden=true;$("#preview-badge").textContent="RENDERED VIDEO";$("#preview-help").textContent="완성된 릴스입니다. 재생해 내용을 확인하세요.";}else{video.hidden=true;video.removeAttribute("src");$("#storyboard").hidden=false;$("#preview-badge").textContent="STORYBOARD";$("#preview-help").innerHTML="위 화면은 구성 미리보기입니다.<br>편집이 끝나면 완성 영상이 표시됩니다.";}const mode=currentMode();$("#storyboard-category").textContent=modeEnglish[mode];$("#storyboard-title").textContent=state.script?.hook||$("#topic").value.trim()||"다음 이야기는\n여기서 시작됩니다.";$("#storyboard-title").style.whiteSpace="pre-line";$("#storyboard-subtitle").textContent=state.script?.scenes?.[0]?.text||($("#brand").value.trim()?`${$("#brand").value.trim()}의 새로운 이야기`:"주제를 입력하고\n나만의 릴스를 만들어 보세요.");$("#storyboard-subtitle").style.whiteSpace="pre-line";const duration=state.job?.artifacts?.duration||Number($("#duration").value)||30;$("#preview-duration").textContent=`${Math.round(duration*10)/10}초`;$("#preview-meta-mode").textContent=modes[mode];}
function sceneCard(scene,index){const card=node("div","scene-card");const heading=node("div","scene-heading");heading.append(node("strong","",`SCENE ${String(index+1).padStart(2,"0")}`));const durationLabel=node("label","","길이 ");const input=node("input","scene-duration");input.type="number";input.min="1";input.max="180";input.step="0.5";input.value=scene.duration||5;input.setAttribute("aria-label",`장면 ${index+1} 길이`);durationLabel.append(input,node("span","","초"));heading.append(durationLabel);const remove=node("button","icon-button");remove.type="button";remove.setAttribute("aria-label",`장면 ${index+1} 삭제`);remove.append(icon("close"));remove.onclick=()=>{state.script=collectScript();state.script.scenes.splice(index,1);state.scriptDirty=true;renderScript();};heading.append(remove);card.append(heading);for(const [kind,label] of [["text","화면 문구"],["narration","내레이션"]]){const field=node("div","field");const fieldLabel=node("label","",label);const textarea=node("textarea",`scene-${kind}`);textarea.rows=2;textarea.value=scene[kind]||"";textarea.id=`scene-${index}-${kind}`;fieldLabel.htmlFor=textarea.id;field.append(fieldLabel,textarea);card.append(field);}card.addEventListener("input",onScriptInput);return card;}
function renderScript() {
  $("#script-panel").hidden = !state.script;
  if (!state.script) {
    $("#scene-list").replaceChildren();
    updateScriptDuration();
    updateActions();
    return;
  }
  setValue("#script-title", state.script.title);
  setValue("#script-hook", state.script.hook);
  setValue("#script-caption", state.script.caption);
  setValue("#script-hashtags", (state.script.hashtags || []).join(" "));
  $("#scene-list").replaceChildren(...(state.script.scenes || []).map(sceneCard));
  updateScriptDuration();
  $("#script-save-state").textContent = state.scriptDirty
    ? "저장하지 않은 수정 사항" : "대본이 저장되어 있습니다.";
  updateActions();
}
function updateScriptDuration(){const total=$$('.scene-duration').reduce((sum,input)=>sum+(Number(input.value)||0),0);$("#script-duration").textContent=`${$$('.scene-card').length}개 장면 · ${Math.round(total*10)/10}초`;}
function onScriptInput(){state.scriptDirty=true;$("#script-save-state").textContent="저장하지 않은 수정 사항";updateScriptDuration();const draft=collectScript();$("#storyboard-title").textContent=draft?.hook||$("#topic").value.trim();}

function renderCurrentJob() {
  const job = state.job;
  $("#job-status-panel").hidden = !job;
  if (!job) {
    renderPreview();
    updateActions();
    return;
  }
  const nextScript = job.script || null;
  if (!state.scriptDirty && JSON.stringify(nextScript) !== JSON.stringify(state.script)) {
    state.script = nextScript;
    renderScript();
  }
  $("#current-status").replaceWith(Object.assign(statusPill(job), { id: "current-status" }));
  $("#current-job-title").textContent = job.title || job.topic || "제목 없는 릴스";
  $("#job-progress").style.width = `${Math.min(100, Math.max(0, Number(job.progress) || 0))}%`;
  const messages = {
    draft: "기획을 다듬고 제작을 시작하세요.", ready: "영상 제작이 완료되었습니다.",
    scheduled: `게시 예약 · ${dateLabel(job.scheduled_at, true)}`, published: "인스타그램 게시가 완료되었습니다.",
  };
  $("#job-message").textContent = job.message || messages[job.status] || "";
  $("#job-error").hidden = !job.error;
  $("#job-error").textContent = typeof job.error === "object" ? JSON.stringify(job.error) : job.error || "";
  const warnings = job.artifacts?.warnings || [];
  $("#job-warnings").hidden = !warnings.length;
  $("#job-warnings").textContent = Array.isArray(warnings) ? warnings.join("\n") : String(warnings);
  renderDownloads(job);
  renderPublishActions(job);
  renderEvents(job);
  const publishing = ["publishing", "published", "approved", "scheduled"].includes(job.status);
  const step = job.status === "generating" ? 2 : job.status === "rendering" ? 3
    : publishing || job.artifacts?.video ? 4 : job.script ? 2 : 1;
  $$(".workflow-step").forEach(element => {
    const value = Number(element.dataset.step);
    element.classList.toggle("active", value === step);
    element.classList.toggle("done", value < step);
  });
  renderPreview();
  updateActions();
}
function renderDownloads(job){const list=$("#download-list");list.replaceChildren();for(const [key,label] of [["video","영상 다운로드"],["cover","커버 이미지"],["subtitles","자막 파일"],["script","대본 파일"],["caption","캡션 파일"]]){const url=jobAssetUrl(job.artifacts?.[key]);if(!url)continue;const link=node("a","download-link");link.href=url;link.download="";link.append(icon(key==="video"?"film":"download"),node("span","",label),icon("arrow"));list.append(link);}}
function renderPublishActions(job){const list=$("#publish-actions");list.replaceChildren();const add=(label,action,style="button-primary")=>{const button=node("button",`button ${style}`,label);button.type="button";button.onclick=()=>jobAction(action);button.disabled=state.busy||activeStatuses.has(job.status);list.append(button);};if(job.status==="failed")add("작업 다시 시도","retry","button-outline");if(job.artifacts?.video&&!activeStatuses.has(job.status)&&job.status!=="published"){if(job.delivery==="approval"&&job.status!=="scheduled"&&job.status!=="approved")add(job.scheduled_at?"승인하고 예약 게시":"승인 후 게시","approve");else add(job.status==="scheduled"?"예약 대신 지금 게시":"인스타그램에 지금 게시","publish","button-dark");}const permalink=job.publish_state?.permalink||job.permalink||job.publish_result?.permalink;if(permalink){const link=node("a","button button-outline","인스타그램에서 보기");link.href=permalink;link.target="_blank";link.rel="noopener";link.append(icon("arrow"));list.append(link);}}
function renderEvents(job){const events=(job.events||[]).slice(-20).reverse();$("#job-events").replaceChildren(...events.map(event=>{const el=node("li","",typeof event==="string"?event:event.message||event.event||event.status||"");if(typeof event==="object"&&(event.at||event.timestamp||event.created_at))el.append(node("time","",dateLabel(event.at||event.timestamp||event.created_at,true)));return el;}));$("#job-log").hidden=!events.length;}
function updateActions(){const working=state.busy||state.uploading>0||activeStatuses.has(state.job?.status);for(const id of ["save-draft","generate-script","run-project","save-script","render-project"]){$("#"+id).disabled=working;}$("#new-job").disabled=state.busy;$("#run-project").textContent=state.busy?"작업 요청 중…":activeStatuses.has(state.job?.status)?statuses[state.job.status]:"릴스 제작 시작";$("#run-project").append(icon("arrow"));$$('#publish-actions button').forEach(button=>button.disabled=working);if(!state.job){$$('.workflow-step').forEach(el=>{el.classList.toggle("active",el.dataset.step==="1");el.classList.remove("done");});}}

function renderJobs(){$("#job-count").textContent=state.jobs.length;const recent=$("#recent-jobs");recent.replaceChildren();if(!state.jobs.length)recent.append(node("p","muted sidebar-empty","첫 번째 릴스를 만들어 보세요."));else state.jobs.slice(0,6).forEach(job=>{const button=node("button",`recent-job${job.id===state.selectedId?" selected":""}`);button.type="button";button.title=job.title||job.topic;button.append(node("span","",job.title||job.topic||"제목 없는 릴스"));button.onclick=()=>openJob(job.id);recent.append(button);});if(state.view==="jobs")renderLibrary();}
function emptyState(title,description,iconName="film"){const el=node("div","empty-state");el.append(icon(iconName),node("h3","",title),node("p","",description));return el;}
function renderLibrary(){const filter=$("#job-filter").value;const jobs=state.jobs.filter(job=>filter==="all"||filter==="active"&&activeStatuses.has(job.status)||filter==="ready"&&["ready","approved"].includes(job.status)||job.status===filter);$("#library-count").textContent=`${jobs.length}개의 콘텐츠`;const library=$("#jobs-library");library.replaceChildren();if(!jobs.length){library.append(emptyState(filter==="all"?"아직 만든 릴스가 없어요":"이 상태의 콘텐츠가 없어요",filter==="all"?"제작 스튜디오에서 첫 번째 이야기를 시작하세요.":"다른 상태를 선택하면 콘텐츠를 볼 수 있습니다."));return;}jobs.forEach(job=>{const card=node("button","library-card");card.type="button";const cover=node("div","library-cover");const imageUrl=jobAssetUrl(job.artifacts?.cover);if(imageUrl){const img=node("img");img.src=imageUrl;img.alt="";img.loading="lazy";cover.append(img);}cover.append(node("span","",modeEnglish[job.mode]||"REEL"),icon(job.mode==="product"?"bag":job.mode==="highlights"?"scissors":"spark"));const body=node("div","library-card-body");const heading=node("div","library-card-heading");heading.append(statusPill(job),node("small","",dateLabel(job.created_at)));body.append(heading,node("h3","",job.title||job.topic||"제목 없는 릴스"),node("p","",`${Math.round(job.artifacts?.duration||job.duration||30)}초 · ${deliveries[job.delivery]||"파일로 내보내기"}`));if(activeStatuses.has(job.status)){const progress=node("div","progress-track"),bar=node("span");bar.style.width=`${Math.min(100,Number(job.progress)||0)}%`;progress.append(bar);body.append(progress);}card.append(cover,body);card.onclick=()=>openJob(job.id);library.append(card);});}

function renderSettingsStatus(){const settings=state.settings;const configured=!!settings.openai_configured;$("#engine-status").replaceChildren(Object.assign(node("span",`status-dot${configured?" connected":""}`),{}),node("span","",configured?"AI 대본 모드":"기본 템플릿 모드"),icon("chevron"));$("#generation-note").textContent=configured?`AI 대본 · ${settings.openai_model||"설정된 모델"} · ${settings.tts_provider==="none"?"내레이션 없음":settings.tts_provider==="openai"?"AI 음성":"로컬 음성"}`:"API 키 없이 기본 템플릿 대본으로 제작합니다.";$("#highlight-selection-note").textContent=configured?"구간을 비우면 AI가 원본 음성을 분석해 주제에 맞는 하이라이트를 선택합니다. 원하는 구간은 초 단위로 지정할 수 있습니다.":"구간을 비우면 영상의 가운데 부분을 선택합니다. AI 구간 선택은 OpenAI 키 연결 후 사용할 수 있습니다.";$("#connection-dot").classList.toggle("connected",!!settings.instagram_configured);$("#connection-label").textContent=settings.instagram_configured?"인스타그램 정보 저장됨":"인스타그램 미연결";$("#connection-detail").textContent=settings.instagram_configured?"게시 시 계정 권한 확인":"설정에서 계정을 연결하세요";const caps=state.capabilities;$("#capabilities-note").textContent=`영상 편집 ${caps.ffmpeg?"준비됨":"FFmpeg 필요"} · 이미지 ${caps.pillow?"준비됨":"Pillow 필요"}${caps.windows_tts?" · 로컬 음성 사용 가능":""}`;}
function openSettings(){const settings=state.settings;setValue("#openai-key","");setValue("#instagram-token","");$("#clear-openai").checked=false;$("#clear-instagram").checked=false;setValue("#openai-model",settings.openai_model||"gpt-4.1-mini");setValue("#tts-provider",settings.tts_provider||"windows");setValue("#tts-model",settings.openai_tts_model||"gpt-4o-mini-tts");setValue("#tts-voice",settings.openai_voice||"coral");setValue("#instagram-user-id",settings.instagram_user_id);setValue("#instagram-login",settings.instagram_login||"instagram");setValue("#instagram-api-version",settings.instagram_api_version||"v23.0");setValue("#public-base-url",settings.public_base_url);$("#share-to-feed").checked=settings.share_to_feed!==false;$("#openai-status").textContent=settings.openai_configured?"키 저장됨":"키 없음 · 템플릿 모드";$("#instagram-status").textContent=settings.instagram_configured?"계정 정보 저장됨":"미연결";$("#openai-tts-fields").hidden=$("#tts-provider").value!=="openai";$("#settings-dialog").showModal();}
async function saveSettings(event){event.preventDefault();const button=$("#save-settings");button.disabled=true;try{const settings={openai_api_key:$("#openai-key").value.trim(),openai_model:$("#openai-model").value.trim(),tts_provider:$("#tts-provider").value,openai_tts_model:$("#tts-model").value.trim(),openai_voice:$("#tts-voice").value,instagram_token:$("#instagram-token").value.trim(),instagram_user_id:$("#instagram-user-id").value.trim(),instagram_login:$("#instagram-login").value,instagram_api_version:$("#instagram-api-version").value.trim(),public_base_url:$("#public-base-url").value.trim().replace(/\/$/,""),share_to_feed:$("#share-to-feed").checked,clear_openai:$("#clear-openai").checked,clear_instagram:$("#clear-instagram").checked};state.settings=await api("/api/settings",{method:"POST",body:settings});renderSettingsStatus();updateSetup();$("#settings-dialog").close();toast("설정을 저장했습니다.");}catch(error){toast(error.message,true);}finally{button.disabled=false;}}

function renderAutomations(){const list=$("#automation-list");list.replaceChildren();$("#automation-count").textContent=`${state.automations.length}개`;if(!state.automations.length){list.append(emptyState("꾸준한 제작을 예약하세요","주제와 시각을 설정하면 매일 한 편씩 제작합니다.","clock"));return;}state.automations.forEach(automation=>{const card=node("article","automation-card");const top=node("div","automation-card-top");top.append(node("h3","",automation.name||"매일 릴스 제작"));const toggle=node("button",`toggle-button${automation.enabled?" enabled":""}`);toggle.type="button";toggle.setAttribute("role","switch");toggle.setAttribute("aria-checked",String(!!automation.enabled));toggle.setAttribute("aria-label",`${automation.name} ${automation.enabled?"일시 정지":"활성화"}`);toggle.append(node("span"));toggle.onclick=async()=>{toggle.disabled=true;try{const result=await api(`/api/automations/${automation.id}`,{method:"PATCH",body:{enabled:!automation.enabled}});const index=state.automations.findIndex(item=>item.id===result.id);if(index>=0)state.automations[index]=result;renderAutomations();toast(result.enabled?"자동화를 활성화했습니다.":"자동화를 일시 정지했습니다.");}catch(error){toast(error.message,true);toggle.disabled=false;}};top.append(toggle);const time=node("div","automation-time",automation.time||"09:00");time.append(node("small","",`매일 · ${automation.timezone||"Asia/Seoul"}`));card.append(top,time,node("p","",`${modes[automation.mode]||"정보 · 지식"} / ${deliveries[automation.delivery]||"파일로 내보내기"}`),node("p","automation-topics",`${(automation.topics||[]).length}개 주제 순환 · ${(automation.topics||[]).join(" → ")}`));if(automation.last_run_at||automation.last_run)card.append(node("p","",`마지막 실행 ${dateLabel(automation.last_run_at||automation.last_run,true)}`));if(automation.last_error)card.append(node("p","job-error",String(automation.last_error)));list.append(card);});}
async function saveAutomation(event){event.preventDefault();const topics=$("#automation-topics").value.split(/\r?\n/).map(topic=>topic.trim()).filter(Boolean);if(!topics.length){toast("자동으로 제작할 주제를 한 줄에 하나씩 입력하세요.",true);return;}const mode=$("#automation-mode").value;if(mode==="highlights"&&!state.assets.some(asset=>asset.kind==="video")){toast("하이라이트 자동화에는 스튜디오에서 먼저 원본 영상을 추가하세요.",true);return;}const button=$('.automation-submit');button.disabled=true;try{const template=collectForm(false);template.mode=mode;template.delivery=$("#automation-delivery").value;template.auto_publish=template.delivery==="auto";delete template.scheduled_at;delete template.title;delete template.topic;const result=await api("/api/automations",{method:"POST",body:{name:$("#automation-name").value.trim(),enabled:$("#automation-enabled").checked,mode,delivery:$("#automation-delivery").value,topics,time:$("#automation-time").value,timezone:$("#automation-timezone").value.trim(),template}});state.automations.unshift(result);renderAutomations();toast(result.enabled?"매일 실행할 자동화를 만들었습니다.":"자동화를 저장했습니다. 활성화하면 매일 실행합니다.");$("#automation-name").value="";$("#automation-topics").value="";$("#automation-enabled").checked=false;}catch(error){toast(error.message,true);}finally{button.disabled=false;}}

async function refreshState({ silent = false } = {}) {
  if (state.polling) return;
  state.polling = true;
  try {
    const result = await api("/api/state");
    const previous = state.job;
    state.jobs = result.jobs || [];
    state.settings = result.settings || {};
    state.capabilities = result.capabilities || {};
    state.automations = result.automations || [];
    state.connected = true;
    state.job = state.selectedId ? state.jobs.find(job => job.id === state.selectedId) || state.job : null;
    renderSettingsStatus();
    renderJobs();
    if (state.job) {
      renderCurrentJob();
      const finished = previous && activeStatuses.has(previous.status) && !activeStatuses.has(state.job.status);
      if (finished && state.job.status !== "failed") {
        toast(state.job.status === "published" ? "릴스가 인스타그램에 게시되었습니다."
          : state.job.artifacts?.video ? "릴스 편집이 완료되었습니다." : "대본이 준비되었습니다. 내용을 확인해 보세요.");
      }
    }
    if (state.view === "automations") renderAutomations();
    if (!state.initialized) {
      state.initialized = true;
      const view = location.hash.slice(1);
      if (Object.hasOwn(viewNames, view)) showView(view);
      else if (!view && !state.jobs.length) showView("setup");
    }
  } catch (error) {
    state.connected = false;
    $("#engine-status").replaceChildren(node("span", "status-dot"), node("span", "", "로컬 서버 연결 대기"));
    $("#connection-label").textContent = "서버에 연결할 수 없습니다";
    $("#connection-detail").textContent = "실행 창을 확인하세요";
    if (!silent) toast(error.message, true);
  } finally {
    state.polling = false;
    updateSetup();
  }
}

$$('[data-view]').forEach(button=>button.addEventListener("click",()=>showView(button.dataset.view)));
$('.brand').addEventListener("click",event=>{event.preventDefault();showView("studio");});
$('#new-job').addEventListener("click",newProject);
$('#project-form').addEventListener("input",()=>{state.formDirty=true;renderSelection();});
$('#project-form').addEventListener("change",()=>{state.formDirty=true;renderSelection();});
$('#project-form').addEventListener("submit",event=>{event.preventDefault();perform("run");});
$('#save-draft').addEventListener("click",async()=>{if(state.busy)return;state.busy=true;updateActions();try{await saveProject({validate:false});}catch(error){toast(error.message,true);}finally{state.busy=false;updateActions();}});
$('#generate-script').addEventListener("click",()=>perform("generate"));
$('#render-project').addEventListener("click",()=>perform("render"));
$('#save-script').addEventListener("click",async()=>{if(state.busy)return;state.busy=true;updateActions();try{await saveProject({validate:false});state.script=collectScript();$('#script-save-state').textContent="대본을 저장했습니다.";}catch(error){toast(error.message,true);}finally{state.busy=false;updateActions();}});
$('#add-scene').addEventListener("click",()=>{state.script=collectScript();if(!state.script)return;state.script.scenes.push({text:"",narration:"",duration:5});state.scriptDirty=true;renderScript();$('.scene-card:last-child .scene-text').focus();});
['#script-title','#script-hook','#script-caption','#script-hashtags'].forEach(selector=>$(selector).addEventListener("input",onScriptInput));
$('#asset-upload').addEventListener("change",event=>uploadFiles(event.target.files));
const dropzone=$('#upload-zone');['dragenter','dragover'].forEach(name=>dropzone.addEventListener(name,event=>{event.preventDefault();dropzone.classList.add("dragging");}));['dragleave','drop'].forEach(name=>dropzone.addEventListener(name,event=>{event.preventDefault();dropzone.classList.remove("dragging");}));dropzone.addEventListener("drop",event=>uploadFiles(event.dataTransfer.files));
$('#open-settings').addEventListener("click",openSettings);$('#engine-status').addEventListener("click",openSettings);$('#close-settings').addEventListener("click",()=>$('#settings-dialog').close());$('#settings-dialog').addEventListener("click",event=>{if(event.target===$('#settings-dialog')){const rect=event.target.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)event.target.close();}});$('#settings-form').addEventListener("submit",saveSettings);$('#tts-provider').addEventListener("change",()=>$('#openai-tts-fields').hidden=$('#tts-provider').value!=="openai");
$('#job-filter').addEventListener("change",renderLibrary);$('#refresh-jobs').addEventListener("click",()=>refreshState());$('#automation-form').addEventListener("submit",saveAutomation);
document.addEventListener("visibilitychange",()=>{if(!document.hidden)refreshState({silent:true});});
window.ReelSetup?.mount($("#view-setup"),{
  openSettings:openSetupSettings,
  showView,
  newJob:newProject,
  refresh:()=>refreshState({silent:true}),
});
$("#settings-guide").addEventListener("click",()=>{
  $("#settings-dialog").close();
  showView("setup");
});
window.addEventListener("hashchange",()=>showView(location.hash.slice(1)||"studio"));
const initialView=location.hash.slice(1);
if(Object.hasOwn(viewNames,initialView))showView(initialView);
renderSelection();renderPreview();refreshState();setInterval(()=>{if(!document.hidden)refreshState({silent:true});},2200);
