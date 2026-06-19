const state = { user: null, view: "dashboard", equipment: [], bookings: [], returns: [] };
const $ = (selector) => document.querySelector(selector);
const money = (value) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(value || 0);
const dateText = (value) => value ? new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "-";
const pretty = (value) => String(value || "").replaceAll("_", " ");
const escapeHtml = (value) => String(value ?? "").replace(/[&<>'"]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[c]));

const menus = {
  user: [
    ["dashboard", "Dashboard"], ["book", "Book Equipment"], ["return", "Return Equipment"],
    ["rentals", "My Rentals"], ["profile", "Profile"]
  ],
  admin: [
    ["dashboard", "Dashboard"], ["equipment", "Equipment Management"], ["customers", "Customer Management"],
    ["returns", "Return Requests"], ["damages", "Damage Reports"], ["deductions", "Deposit Deduction"],
    ["statuses", "Status Updates"], ["reports", "Reports"]
  ]
};

const titles = {
  dashboard: ["DASHBOARD", "Dashboard", "A live view of your rental operations."], book: ["EQUIPMENT CATALOGUE", "Book Equipment", "Choose available equipment and submit a rental request."],
  return: ["RETURN CENTRE", "Return Equipment", "Request a return for an active rental."], rentals: ["RENTAL HISTORY", "My Rentals", "Track every booking from request to return."],
  profile: ["ACCOUNT", "Profile", "Review and update your personal details."], equipment: ["ADMIN INVENTORY", "Equipment Management", "Add equipment and control stock availability."],
  customers: ["ADMIN CUSTOMERS", "Customer Management", "View customer accounts and rental activity."], returns: ["ADMIN RETURNS", "Return Requests", "Inspect incoming equipment and complete returns."],
  damages: ["ADMIN CLAIMS", "Damage Reports", "Review damaged or lost equipment cases."], deductions: ["ADMIN FINANCE", "Deposit Deduction", "Approve or reject proposed deposit deductions."],
  statuses: ["ADMIN WORKFLOW", "Status Updates", "Update booking and return workflow states."], reports: ["ADMIN ANALYTICS", "Reports", "Review operational and financial totals."]
};

function toast(message, error = false) {
  const el = $("#toast"); el.textContent = message; el.className = `toast show${error ? " error" : ""}`;
  setTimeout(() => el.className = "toast", 2600);
}

async function api(url, options = {}) {
  const response = await fetch(url, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  let data = {}; try { data = await response.json(); } catch (_) {}
  if (!response.ok) throw new Error(data.details?.join?.(", ") || data.error || "Request failed");
  return data;
}

function badge(value) { return `<span class="badge ${value}">${escapeHtml(pretty(value))}</span>`; }
function table(headers, rows, empty = "No records found") {
  return `<div class="panel"><div class="table-wrap"><table><thead><tr>${headers.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.join("")}</tbody></table>${rows.length ? "" : `<div class="empty">${empty}</div>`}</div></div>`;
}
function cards(items) { return `<div class="summary-grid">${items.map((x,i) => `<article class="summary-card"><span class="summary-icon ${x[2] || ""}">${String(i+1).padStart(2,"0")}</span><div><small>${x[0]}</small><strong>${x[1]}</strong></div></article>`).join("")}</div>`; }

function openModal(html) { $("#modalContent").innerHTML = `<div class="modal-body">${html}</div>`; $("#modal").showModal(); document.querySelectorAll(".modal-close").forEach(b => b.onclick = () => $("#modal").close()); }
function modalHead(title, subtitle = "") { return `<div class="modal-head"><div><h2>${title}</h2>${subtitle ? `<p class="muted">${subtitle}</p>` : ""}</div><button type="button" class="modal-close">x</button></div>`; }

async function boot() {
  try { state.user = (await api("/api/auth/me")).user; showApp(); } catch (_) { $("#loginPage").classList.remove("hidden"); }
}

function showApp() {
  $("#loginPage").classList.add("hidden"); $("#appShell").classList.remove("hidden");
  /* Clear all login / auth forms so no details persist outside the app */
  document.querySelectorAll("#loginPage form").forEach(f => f.reset());
  ["#resetEmail","#newPassEmail","#newPassOtp"].forEach(s => { const el = $(s); if (el) el.value = ""; });
  $("#forgotNotice").classList.add("hidden");
  /* Reset any revealed passwords back to hidden */
  document.querySelectorAll("#loginPage .password-wrap input").forEach(i => i.type = "password");
  document.querySelectorAll("#loginPage .toggle-pw").forEach(b => b.textContent = "\ud83d\udc41");
  $("#portalName").textContent = state.user.role === "admin" ? "Admin operations" : "Customer rental portal";
  $("#sidebarName").textContent = state.user.name; $("#sidebarRole").textContent = state.user.role === "admin" ? "Administrator" : "Customer";
  $("#userInitials").textContent = state.user.name.split(" ").map(x => x[0]).slice(0,2).join("").toUpperCase();
  $("#navigation").innerHTML = menus[state.user.role].map(item => `<button class="nav-item" data-view="${item[0]}">${item[1]}</button>`).join("");
  document.querySelectorAll(".nav-item").forEach(button => button.onclick = () => { toggleSidebar(false); loadView(button.dataset.view); });
  loadView("dashboard");
}

async function loadView(view) {
  state.view = view; const info = titles[view];
  $("#pageEyebrow").textContent = info[0]; $("#pageTitle").textContent = info[1]; $("#pageSubtitle").textContent = info[2]; $("#headerAction").innerHTML = "";
  document.querySelectorAll(".nav-item").forEach(b => b.classList.toggle("active", b.dataset.view === view));
  $("#pageContent").innerHTML = `<div class="loading">Loading ${info[1].toLowerCase()}...</div>`;
  try { await renderers[view](); } catch (error) { $("#pageContent").innerHTML = `<div class="panel empty">${escapeHtml(error.message)}</div>`; toast(error.message, true); }
}

const renderers = {
  async dashboard() {
    const data = await api("/api/dashboard");
    if (state.user.role === "user") {
      const rows = data.recent.map(b => `<tr><td><strong>${escapeHtml(b.equipment_name)}</strong><small>${escapeHtml(b.equipment_code)}</small></td><td>${dateText(b.start_date)} - ${dateText(b.end_date)}</td><td>${money(b.total_amount)}</td><td>${badge(b.is_overdue ? "overdue" : b.status)}</td></tr>`);
      $("#pageContent").innerHTML = cards([["Total rentals",data.total_rentals],["Active",data.active,"green"],["Pending",data.pending,"amber"],["Returned",data.returned]]) + table(["Equipment","Rental period","Amount","Status"], rows, "You have no rentals yet.");
    } else {
      const rows = data.recent.map(r => `<tr><td><strong>${escapeHtml(r.equipment_name)}</strong><small>${escapeHtml(r.equipment_code)}</small></td><td>${escapeHtml(r.customer_name)}</td><td>${dateText(r.return_due_date)}</td><td>${badge(r.is_overdue ? "overdue" : r.status)}</td></tr>`);
      $("#pageContent").innerHTML = cards([["Equipment",data.equipment],["Customers",data.customers],["Pending bookings",data.pending_bookings,"amber"],["Open claims",data.claims,"red"]]) + `<div class="content-grid">${table(["Equipment","Customer","Due date","Status"],rows,"No return activity yet.")}<aside class="panel side-panel"><h3>Financial snapshot</h3><div class="metric-line"><span>Repair exposure</span><b>${money(data.repair_cost)}</b></div><div class="metric-line"><span>Deposit deductions</span><b>${money(data.deductions)}</b></div><div class="metric-line"><span>Available units</span><b>${data.available}</b></div><div class="metric-line"><span>Overdue returns</span><b>${data.overdue}</b></div></aside></div>`;
    }
  },
  async book() {
    state.equipment = await api("/api/equipment");
    const available = state.equipment.filter(e => e.status === "available" && e.stock_available > 0);
    $("#pageContent").innerHTML = `<div class="equipment-grid">${available.map(e => `<article class="equipment-card"><div class="equipment-visual">${escapeHtml(e.category.slice(0,3).toUpperCase())}</div><small class="muted">${escapeHtml(e.category)} / ${escapeHtml(e.code)}</small><h3>${escapeHtml(e.name)}</h3><p>${escapeHtml(e.description)}</p><div class="equipment-meta"><span>Daily rate<b>${money(e.daily_rate)}</b></span><span>Deposit<b>${money(e.deposit_amount)}</b></span><span>Available<b>${e.stock_available}</b></span></div><button class="primary" data-book="${e.id}">Book now</button></article>`).join("")}</div>`;
    document.querySelectorAll("[data-book]").forEach(b => b.onclick = () => showBooking(Number(b.dataset.book)));
  },
  async return() {
    state.bookings = await api("/api/bookings");
    const eligible = state.bookings.filter(b => ["approved","active"].includes(b.status));
    const rows = eligible.map(b => `<tr><td><strong>${escapeHtml(b.equipment_name)}</strong><small>${escapeHtml(b.equipment_code)}</small></td><td>${dateText(b.end_date)}</td><td>${money(b.deposit_amount)}</td><td>${badge(b.status)}</td><td><button class="small-btn" data-return="${b.id}">Request return</button></td></tr>`);
    $("#pageContent").innerHTML = table(["Equipment","Due date","Deposit","Status","Action"],rows,"No active rentals are ready for return.");
    document.querySelectorAll("[data-return]").forEach(b => b.onclick = () => showReturnRequest(Number(b.dataset.return)));
  },
  async rentals() {
    state.bookings = await api("/api/bookings");
    const rows = state.bookings.map(b => `<tr><td>#${b.id}</td><td><strong>${escapeHtml(b.equipment_name)}</strong><small>${escapeHtml(b.equipment_code)}</small></td><td>${dateText(b.start_date)} - ${dateText(b.end_date)}</td><td>${b.days} day(s)</td><td>${money(b.total_amount)}</td><td>${badge(b.is_overdue ? "overdue" : b.status)}</td></tr>`);
    $("#pageContent").innerHTML = table(["Booking","Equipment","Rental period","Duration","Amount","Status"],rows,"No booking history yet.");
  },
  async profile() {
    const p = await api("/api/profile");
    $("#pageContent").innerHTML = `<section class="panel profile-card"><div class="profile-header"><span class="avatar">${escapeHtml(p.name[0])}</span><div><h2>${escapeHtml(p.name)}</h2><small>${escapeHtml(pretty(p.role))} account</small></div></div><form id="profileForm"><div class="form-grid"><label class="field">Full name<input name="name" value="${escapeHtml(p.name)}" required></label><label class="field">Phone number<input name="phone" value="${escapeHtml(p.phone || "")}"></label><label class="field wide">Email address<input value="${escapeHtml(p.email)}" disabled></label></div><div class="form-actions"><button class="primary">Save profile</button></div></form></section>`;
    $("#profileForm").onsubmit = saveProfile;
  },
  async equipment() {
    state.equipment = await api("/api/equipment");
    $("#headerAction").innerHTML = `<button class="primary" id="addEquipment">+ Add equipment</button>`; $("#addEquipment").onclick = showEquipmentForm;
    const rows = state.equipment.map(e => `<tr><td><strong>${escapeHtml(e.name)}</strong><small>${escapeHtml(e.code)}</small></td><td>${escapeHtml(e.category)}</td><td>${money(e.daily_rate)}</td><td>${e.stock_available} / ${e.stock_total}</td><td>${badge(e.condition)}</td><td>${badge(e.status)}</td><td><button class="small-btn" data-edit-equipment="${e.id}">Edit</button></td></tr>`);
    $("#pageContent").innerHTML = table(["Equipment","Category","Daily rate","Stock","Condition","Status","Action"],rows,"No equipment in inventory.");
    document.querySelectorAll("[data-edit-equipment]").forEach(b => b.onclick = () => showEquipmentForm(Number(b.dataset.editEquipment)));
  },
  async customers() {
    const customers = await api("/api/customers");
    const rows = customers.map(c => `<tr><td><strong>${escapeHtml(c.name)}</strong><small>Customer #${c.id}</small></td><td>${escapeHtml(c.email)}</td><td>${escapeHtml(c.phone || "-")}</td><td>${c.rental_count}</td><td>${money(c.total_spend)}</td><td>${badge(c.active ? "active" : "disabled")}</td><td><button class="small-btn ${c.active ? "secondary" : ""}" data-customer="${c.id}:${c.active ? 0 : 1}">${c.active ? "Disable" : "Enable"}</button></td></tr>`);
    $("#pageContent").innerHTML = table(["Customer","Email","Phone","Rentals","Total value","Account","Action"],rows,"No customers found.");
    document.querySelectorAll("[data-customer]").forEach(b => b.onclick = () => updateCustomer(b.dataset.customer));
  },
  async returns() {
    state.returns = await api("/api/returns");
    const rows = state.returns.map(r => `<tr><td>#${r.id}</td><td><strong>${escapeHtml(r.equipment_name)}</strong><small>${escapeHtml(r.equipment_code)}</small></td><td>${escapeHtml(r.customer_name)}</td><td>${dateText(r.actual_return_date || r.return_due_date)}</td><td>${badge(r.status)}</td><td><button class="small-btn" data-inspect="${r.id}">${r.return_request_status === "processed" ? "View" : "Inspect"}</button></td></tr>`);
    $("#pageContent").innerHTML = table(["Request","Equipment","Customer","Return date","Status","Action"],rows,"No return requests.");
    document.querySelectorAll("[data-inspect]").forEach(b => b.onclick = () => showInspection(Number(b.dataset.inspect)));
  },
  async damages() {
    state.returns = await api("/api/returns"); const records = state.returns.filter(r => r.status === "claim_pending" || ["damaged","lost"].includes(r.condition));
    const rows = records.map(r => `<tr><td>#${r.id}</td><td><strong>${escapeHtml(r.equipment_name)}</strong><small>${escapeHtml(r.equipment_code)}</small></td><td>${escapeHtml(r.customer_name)}</td><td>${badge(r.condition)}</td><td>${escapeHtml(r.damage_remarks || "-")}</td><td>${money(r.repair_cost)}</td><td>${badge(r.status)}</td></tr>`);
    $("#pageContent").innerHTML = table(["Report","Equipment","Customer","Condition","Damage remarks","Repair cost","Status"],rows,"No damage reports.");
  },
  async deductions() {
    state.returns = await api("/api/returns"); const records = state.returns.filter(r => r.deposit_deduction > 0 || r.status === "claim_pending");
    const rows = records.map(r => `<tr><td>#${r.id}</td><td>${escapeHtml(r.customer_name)}</td><td><strong>${escapeHtml(r.equipment_name)}</strong></td><td>${money(r.deposit_amount)}</td><td>${money(r.deposit_deduction)}</td><td>${badge(r.deduction_status)}</td><td><div class="actions"><button class="small-btn" data-deduct="${r.id}:approved">Approve</button><button class="small-btn secondary" data-deduct="${r.id}:rejected">Reject</button></div></td></tr>`);
    $("#pageContent").innerHTML = table(["Claim","Customer","Equipment","Deposit","Proposed deduction","Decision","Action"],rows,"No deductions require review.");
    document.querySelectorAll("[data-deduct]").forEach(b => b.onclick = () => decideDeduction(b.dataset.deduct));
  },
  async statuses() {
    const [bookings, returns] = await Promise.all([api("/api/bookings"), api("/api/returns")]);
    const bookingRows = bookings.map(b => `<tr><td>#${b.id}</td><td>${escapeHtml(b.customer_name)}</td><td>${escapeHtml(b.equipment_name)}</td><td>${badge(b.status)}</td><td><select data-booking-status="${b.id}">${["pending","approved","active","return_requested","returned","rejected","cancelled"].map(s => `<option ${s===b.status?"selected":""}>${s}</option>`).join("")}</select></td></tr>`);
    const returnRows = returns.map(r => `<tr><td>#${r.id}</td><td>${escapeHtml(r.customer_name)}</td><td>${escapeHtml(r.equipment_name)}</td><td>${badge(r.status)}</td><td><select data-return-status="${r.id}">${["due","overdue","returned","inspection","claim_pending","closed"].map(s => `<option ${s===r.status?"selected":""}>${s}</option>`).join("")}</select></td></tr>`);
    $("#pageContent").innerHTML = `<div class="panel-head"><div><h2>Booking statuses</h2><p>Approve or move customer booking requests.</p></div></div>${table(["Booking","Customer","Equipment","Current","Update"],bookingRows)}<div style="height:18px"></div><div class="panel-head"><div><h2>Return statuses</h2><p>Control return and claim workflow states.</p></div></div>${table(["Return","Customer","Equipment","Current","Update"],returnRows)}`;
    document.querySelectorAll("[data-booking-status]").forEach(s => s.onchange = () => updateBookingStatus(s.dataset.bookingStatus,s.value));
    document.querySelectorAll("[data-return-status]").forEach(s => s.onchange = () => updateReturnStatus(s.dataset.returnStatus,s.value));
  },
  async reports() {
    const data = await api("/api/dashboard");
    $("#headerAction").innerHTML = `<a class="primary" href="/api/reports/returns.csv" style="text-decoration:none">Download CSV</a>`;
    $("#pageContent").innerHTML = cards([["Total bookings",data.bookings],["Return records",data.returns],["Open claims",data.claims,"red"],["Overdue",data.overdue,"amber"]]) + `<section class="panel side-panel"><h3>Financial report</h3><div class="metric-line"><span>Estimated repair costs</span><b>${money(data.repair_cost)}</b></div><div class="metric-line"><span>Deposit deductions</span><b>${money(data.deductions)}</b></div><div class="metric-line"><span>Customers</span><b>${data.customers}</b></div><div class="metric-line"><span>Inventory units available</span><b>${data.available}</b></div></section>`;
  }
};

function showBooking(id) {
  const e = state.equipment.find(x => x.id === id);
  openModal(`${modalHead("Book equipment", `${escapeHtml(e.name)} / ${money(e.daily_rate)} per day`)}<form id="bookingForm"><input type="hidden" name="equipment_id" value="${e.id}"><div class="form-grid"><label class="field">Start date<input type="date" name="start_date" required></label><label class="field">End date<input type="date" name="end_date" required></label><label class="field wide">Purpose<textarea name="purpose" rows="3" placeholder="Shoot, event, production..."></textarea></label></div><div class="notice">Security deposit: <b>${money(e.deposit_amount)}</b>. Final rental amount is calculated from the selected duration.</div><div class="form-actions"><button type="button" class="ghost modal-close">Cancel</button><button class="primary">Submit booking</button></div></form>`);
  $("#bookingForm").onsubmit = async event => { event.preventDefault(); try { await api("/api/bookings",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}); $("#modal").close(); toast("Booking request submitted"); loadView("rentals"); } catch(e){toast(e.message,true);} };
}

function showReturnRequest(id) {
  const b = state.bookings.find(x => x.id === id);
  openModal(`${modalHead("Return equipment", `${escapeHtml(b.equipment_name)} / Booking #${b.id}`)}<form id="returnRequestForm"><input type="hidden" name="booking_id" value="${b.id}"><div class="form-grid"><label class="field">Return date<input type="date" name="actual_return_date" value="${new Date().toISOString().slice(0,10)}" required></label><label class="field wide">Return notes<textarea name="notes" rows="3" placeholder="Mention accessories or any known issue"></textarea></label></div><div class="form-actions"><button type="button" class="ghost modal-close">Cancel</button><button class="primary">Submit return request</button></div></form>`);
  $("#returnRequestForm").onsubmit = async event => { event.preventDefault(); try { await api("/api/returns/request",{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}); $("#modal").close(); toast("Return request submitted"); loadView("rentals"); } catch(e){toast(e.message,true);} };
}

function showEquipmentForm(id = null) {
  const e = id ? state.equipment.find(x => x.id === id) : {};
  openModal(`${modalHead(id ? "Edit equipment" : "Add equipment")}<form id="equipmentForm"><div class="form-grid"><label class="field">Asset code<input name="code" value="${escapeHtml(e.code||"")}" ${id?"disabled":""} required></label><label class="field">Equipment name<input name="name" value="${escapeHtml(e.name||"")}" required></label><label class="field">Category<select name="category">${["Camera","Lens","Lighting","Audio","Gimbal","Accessory"].map(x=>`<option ${x===e.category?"selected":""}>${x}</option>`).join("")}</select></label><label class="field">Daily rate<input type="number" min="0" name="daily_rate" value="${e.daily_rate||0}" required></label><label class="field">Deposit amount<input type="number" min="0" name="deposit_amount" value="${e.deposit_amount||0}" required></label><label class="field">Total stock<input type="number" min="0" name="stock_total" value="${e.stock_total??1}" required></label>${id?`<label class="field">Available stock<input type="number" min="0" name="stock_available" value="${e.stock_available}"></label><label class="field">Condition<select name="condition">${["excellent","good","fair","damaged"].map(x=>`<option ${x===e.condition?"selected":""}>${x}</option>`).join("")}</select></label><label class="field">Status<select name="status">${["available","maintenance","retired"].map(x=>`<option ${x===e.status?"selected":""}>${x}</option>`).join("")}</select></label>`:""}<label class="field wide">Description<textarea name="description" rows="3">${escapeHtml(e.description||"")}</textarea></label></div><div class="form-actions"><button type="button" class="ghost modal-close">Cancel</button><button class="primary">Save equipment</button></div></form>`);
  $("#equipmentForm").onsubmit = async event => { event.preventDefault(); const payload=Object.fromEntries(new FormData(event.target)); try { await api(id?`/api/equipment/${id}`:"/api/equipment",{method:id?"PATCH":"POST",body:JSON.stringify(payload)}); $("#modal").close(); toast("Equipment saved"); loadView("equipment"); } catch(e){toast(e.message,true);} };
}

async function showInspection(id) {
  const r = await api(`/api/returns/${id}`);
  openModal(`${modalHead(`Return inspection #${r.id}`, `${escapeHtml(r.equipment_name)} / ${escapeHtml(r.customer_name)}`)}<div class="detail-grid"><div><small>Due date</small><b>${dateText(r.return_due_date)}</b></div><div><small>Deposit</small><b>${money(r.deposit_amount)}</b></div><div><small>Status</small>${badge(r.status)}</div></div>${r.recommendation?`<div class="notice"><b>Recommendation</b><br>${escapeHtml(r.recommendation)}</div>`:""}<form id="inspectionForm"><div class="form-grid"><label class="field">Actual return date<input type="date" name="actual_return_date" value="${r.actual_return_date||new Date().toISOString().slice(0,10)}" required></label><label class="field">Condition<select name="condition">${["excellent","good","fair","damaged","lost"].map(x=>`<option ${x===r.condition?"selected":""}>${x}</option>`).join("")}</select></label><label class="field">Repair cost<input type="number" name="repair_cost" min="0" value="${r.repair_cost||0}"></label><label class="field wide">Damage remarks<textarea name="damage_remarks" rows="3">${escapeHtml(r.damage_remarks||"")}</textarea></label></div><div class="form-actions"><button type="button" class="ghost modal-close">Close</button><button class="primary">Process inspection</button></div></form>`);
  $("#inspectionForm").onsubmit = async event => {event.preventDefault();try{await api(`/api/returns/${id}/process`,{method:"POST",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))});$("#modal").close();toast("Inspection processed");loadView("returns");}catch(e){toast(e.message,true);}};
}

async function saveProfile(event) { event.preventDefault(); try { const p=await api("/api/profile",{method:"PATCH",body:JSON.stringify(Object.fromEntries(new FormData(event.target)))}); state.user={...state.user,...p}; $("#sidebarName").textContent=p.name; toast("Profile updated"); } catch(e){toast(e.message,true);} }
async function decideDeduction(value) { const [id,decision]=value.split(":"); try{await api(`/api/returns/${id}/deduction`,{method:"PATCH",body:JSON.stringify({decision})});toast(`Deduction ${decision}`);loadView("deductions");}catch(e){toast(e.message,true);} }
async function updateBookingStatus(id,status) { try{await api(`/api/bookings/${id}/status`,{method:"PATCH",body:JSON.stringify({status})});toast("Booking status updated");loadView("statuses");}catch(e){toast(e.message,true);loadView("statuses");} }
async function updateReturnStatus(id,status) { try{await api(`/api/returns/${id}/status`,{method:"PATCH",body:JSON.stringify({status})});toast("Return status updated");}catch(e){toast(e.message,true);loadView("statuses");} }
async function updateCustomer(value) { const [id,active]=value.split(":"); try{await api(`/api/customers/${id}`,{method:"PATCH",body:JSON.stringify({active:active==="1"})});toast("Customer account updated");loadView("customers");}catch(e){toast(e.message,true);} }


/* ---------- Auth view switching ---------- */
function showAuthView(viewId) {
  ["loginView","registerView","forgotView","resetView","setPasswordView"].forEach(id => {
    const el = document.getElementById(id);
    if (el) {
      el.classList.toggle("hidden", id !== viewId);
      if (id !== viewId) el.querySelectorAll("form").forEach(f => f.reset());
    }
  });
  $("#forgotNotice").classList.add("hidden");
}

$("#showForgot").onclick = () => showAuthView("forgotView");
$("#showRegister").onclick = () => showAuthView("registerView");
$("#showLoginFromRegister").onclick = () => showAuthView("loginView");
$("#showLoginFromForgot").onclick = () => showAuthView("loginView");
$("#showLoginFromReset").onclick = () => showAuthView("loginView");
$("#showLoginFromSetPass").onclick = () => showAuthView("loginView");

/* ---------- Login ---------- */
$("#loginForm").onsubmit = async event => {
  event.preventDefault();
  const formData = Object.fromEntries(new FormData(event.target));
  const identifier = (formData.identifier || "").trim();
  const payload = { password: formData.password };
  if (identifier.includes("@")) {
    payload.email = identifier;
  } else {
    payload.phone = identifier;
  }
  try {
    const data = await api("/api/auth/login", { method: "POST", body: JSON.stringify(payload) });
    state.user = data.user;
    showApp();
  } catch (e) { toast(e.message, true); }
};

/* ---------- Register ---------- */
$("#registerForm").onsubmit = async event => {
  event.preventDefault();
  try {
    const data = await api("/api/auth/register", { method: "POST", body: JSON.stringify(Object.fromEntries(new FormData(event.target))) });
    state.user = data.user;
    toast("Account created successfully!");
    showApp();
  } catch (e) { toast(e.message, true); }
};

/* ---------- Forgot Password (send OTP) ---------- */
$("#forgotForm").onsubmit = async event => {
  event.preventDefault();
  const formData = Object.fromEntries(new FormData(event.target));
  const identifier = (formData.identifier || "").trim();
  const isEmail = identifier.includes("@");
  const payload = isEmail ? { email: identifier } : { phone: identifier };
  try {
    const data = await api("/api/auth/forgot-password", { method: "POST", body: JSON.stringify(payload) });
    $("#resetEmail").value = data.email || identifier;
    const notice = $("#forgotNotice");
    if (data.dev_otp) {
      notice.innerHTML = `<div class="notice info">Development OTP: <strong>${data.dev_otp}</strong>. Configure SMTP/SMS to send it automatically.</div>`;
      notice.classList.remove("hidden");
      $("#resetSubtitle").textContent = `Use the development OTP shown below for ${identifier}`;
    } else {
      notice.classList.add("hidden");
      $("#resetSubtitle").textContent = `We sent a 6-digit OTP to ${identifier}`;
    }
    showAuthView("resetView");
    toast(data.message);
  } catch (e) { toast(e.message, true); }
};

/* ---------- Step 1: Verify OTP ---------- */
$("#verifyOtpForm").onsubmit = async event => {
  event.preventDefault();
  const formData = Object.fromEntries(new FormData(event.target));
  try {
    await api("/api/auth/verify-otp", { method: "POST", body: JSON.stringify(formData) });
    toast("OTP verified successfully!");
    $("#newPassEmail").value = formData.email;
    $("#newPassOtp").value = formData.otp;
    showAuthView("setPasswordView");
  } catch (e) { toast(e.message, true); }
};

/* ---------- Step 2: Set New Password ---------- */
$("#setPasswordForm").onsubmit = async event => {
  event.preventDefault();
  const formData = Object.fromEntries(new FormData(event.target));
  const confirmPass = $("#confirmPassword").value;
  if (formData.password !== confirmPass) {
    toast("Passwords do not match", true);
    return;
  }
  try {
    const data = await api("/api/auth/reset-password", { method: "POST", body: JSON.stringify(formData) });
    toast(data.message || "Password reset successfully!");
    ["#setPasswordForm","#verifyOtpForm","#forgotForm","#loginForm","#registerForm"].forEach(s => { const f = $(s); if (f) f.reset(); });
    $("#resetEmail").value = "";
    $("#newPassEmail").value = "";
    $("#newPassOtp").value = "";
    $("#forgotNotice").classList.add("hidden");
    showAuthView("loginView");
  } catch (e) { toast(e.message, true); }
};

/* ---------- Logout ---------- */
$("#logoutBtn").onclick = async () => {
  await api("/api/auth/logout", { method: "POST" });
  state.user = null;
  $("#appShell").classList.add("hidden");
  /* Clear all auth forms so no details linger */
  document.querySelectorAll("#loginPage form").forEach(f => f.reset());
  ["#resetEmail","#newPassEmail","#newPassOtp"].forEach(s => { const el = $(s); if (el) el.value = ""; });
  $("#forgotNotice").classList.add("hidden");
  document.querySelectorAll("#loginPage .password-wrap input").forEach(i => i.type = "password");
  document.querySelectorAll("#loginPage .toggle-pw").forEach(b => b.textContent = "\ud83d\udc41");
  $("#loginPage").classList.remove("hidden");
  showAuthView("loginView");
  toast("Logged out");
};

/* ---------- Show / Hide password toggle ---------- */
document.addEventListener("click", e => {
  const btn = e.target.closest(".toggle-pw");
  if (!btn) return;
  const input = btn.parentElement.querySelector("input");
  if (!input) return;
  const showing = input.type === "text";
  input.type = showing ? "password" : "text";
  btn.textContent = showing ? "\ud83d\udc41" : "\ud83d\ude48";
  btn.setAttribute("aria-label", showing ? "Show password" : "Hide password");
});

/* ---------- Mobile sidebar toggle ---------- */
function toggleSidebar(open) {
  const sidebar = $("#sidebar");
  const backdrop = $("#sidebarBackdrop");
  if (open === undefined) open = !sidebar.classList.contains("open");
  sidebar.classList.toggle("open", open);
  backdrop.classList.toggle("active", open);
}
$("#menuToggle").onclick = () => toggleSidebar();
$("#sidebarBackdrop").onclick = () => toggleSidebar(false);

boot();

