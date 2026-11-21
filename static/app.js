"use strict";

/* SplitEase front end.
 * Talks to the REST API described in docs/API.md.
 * All money is integer cents; parseMoney()/formatMoney() convert to and from "12.34". */

const state = {
  groups: [],
  groupId: null,
  group: null,
  expenses: [],
  balances: {},
  plan: [],
  editingId: null,
  formGroupId: null,
};

const $ = (id) => document.getElementById(id);

/* ---------------------------------------------------------------- helpers */
function el(tag, props = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value);
  }
  for (const child of children) node.append(child);
  return node;
}

/* "12.34" -> 1234. Returns null if the text is not a plain amount with at most 2 decimals.
 * Done with string maths, not floats, so 1.005 or 0.29 can never be off by a cent. */
function parseMoney(text) {
  const clean = String(text).trim();
  if (!/^\d+(\.\d{1,2})?$/.test(clean)) return null;
  const [whole, fraction = ""] = clean.split(".");
  return Number(whole) * 100 + Number(fraction.padEnd(2, "0"));
}

/* 1234 -> "12.34", -50 -> "-0.50" */
function formatMoney(cents) {
  const sign = cents < 0 ? "-" : "";
  const abs = Math.abs(cents);
  return sign + Math.floor(abs / 100) + "." + String(abs % 100).padStart(2, "0");
}

let messageTimer = null;
function showMessage(text, ok = false) {
  const box = $("message");
  box.textContent = text;
  box.className = ok ? "message ok" : "message";
  box.hidden = false;
  clearTimeout(messageTimer);
  if (ok) messageTimer = setTimeout(() => { box.hidden = true; }, 3500);
}

function clearMessage() {
  clearTimeout(messageTimer);
  $("message").hidden = true;
}

/* Wrap an event handler: stop the browser's default action and show any error. */
function guard(handler) {
  return async (event) => {
    if (event && event.preventDefault) event.preventDefault();
    try {
      await handler(event);
    } catch (error) {
      showMessage(error.message);
    }
  };
}

async function api(method, path, body) {
  const options = { method, headers: {} };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch("/api" + path, options);
  } catch (networkError) {
    throw new Error("Cannot reach the server. Start it with: python -m flask --app app run");
  }
  if (response.status === 204) return null;
  let data = null;
  try {
    data = await response.json();
  } catch (parseError) {
    /* response had no JSON body */
  }
  if (!response.ok) {
    throw new Error((data && data.error) || `Request failed (${response.status})`);
  }
  return data;
}

function memberName(id) {
  const member = state.group && state.group.members.find((m) => m.id === Number(id));
  return member ? member.name : `#${id}`;
}

/* ---------------------------------------------------------------- loading */
async function loadGroups() {
  state.groups = await api("GET", "/groups");
  renderGroups();
}

async function loadGroup() {
  if (state.groupId === null) {
    state.group = null;
    renderGroupView();
    return;
  }
  const id = state.groupId;
  const [group, expenses, balances, plan] = await Promise.all([
    api("GET", `/groups/${id}`),
    api("GET", `/groups/${id}/expenses`),
    api("GET", `/groups/${id}/balances`),
    api("GET", `/groups/${id}/settle-plan`),
  ]);
  state.group = group;
  state.expenses = expenses;
  state.balances = balances.balances;
  state.plan = plan.payments;
  renderGroupView();
}

async function selectGroup(id) {
  clearMessage();
  state.groupId = id;
  state.group = null;
  setEditMode(null);
  $("expense-form").reset();
  renderGroups();
  await loadGroup();
}

/* -------------------------------------------------------------- rendering */
function renderGroups() {
  const items = state.groups.map((group) => {
    const button = el("button", { type: "button", class: "secondary small-btn" }, group.name);
    button.addEventListener("click", guard(() => selectGroup(group.id)));
    const item = el("li", { class: group.id === state.groupId ? "selected" : "" }, button);
    return item;
  });
  $("group-list").replaceChildren(...items);
  $("no-groups").hidden = state.groups.length > 0;
}

function renderGroupView() {
  const visible = state.group !== null;
  $("group-view").hidden = !visible;
  $("welcome").hidden = visible;
  if (!visible) return;

  $("group-title").textContent = state.group.name;
  renderMembers();
  renderExpenseForm();
  renderExpenses();
  renderBalances();
  renderPlan();
}

function renderMembers() {
  const members = state.group.members;
  const items = members.map((member) => {
    const remove = el("button", { type: "button", class: "danger small-btn" }, "Remove");
    remove.addEventListener("click", guard(() => removeMember(member)));
    return el("li", {}, el("span", {}, member.name), remove);
  });
  $("member-list").replaceChildren(...items);
  $("no-members").hidden = members.length > 0;
}

function renderExpenseForm(fresh = false) {
  const members = state.group.members;
  const previous = fresh || state.formGroupId !== state.groupId ? null : readParticipants();

  const payer = $("expense-payer");
  const selected = payer.value;
  payer.replaceChildren(...members.map((m) => el("option", { value: String(m.id) }, m.name)));
  if (!fresh && members.some((m) => String(m.id) === selected)) payer.value = selected;

  renderParticipants(previous);
  state.formGroupId = state.groupId;
}

/* One row per member: a checkbox, plus an amount / percent box for EXACT and PERCENT. */
function renderParticipants(previous = null) {
  const split = $("expense-split").value;
  const rows = state.group.members.map((member) => {
    const old = previous ? previous[member.id] : null;
    const checkbox = el("input", { type: "checkbox", id: `participant-${member.id}` });
    checkbox.checked = old ? old.checked : true;
    const label = el("label", { for: `participant-${member.id}` }, member.name);
    const row = el("div", { class: "participant" }, checkbox, label);
    if (split !== "EQUAL") {
      const isPercent = split === "PERCENT";
      const input = el("input", {
        type: "number",
        min: "0",
        step: "0.01",
        id: `value-${member.id}`,
        placeholder: isPercent ? "%" : "0.00",
        "aria-label": `${isPercent ? "Percent" : "Amount"} for ${member.name}`,
      });
      if (isPercent) input.max = "100";
      input.value = old && old.value ? old.value : "";
      row.append(input);
    }
    return row;
  });
  $("participants").replaceChildren(...rows);
}

function readParticipants() {
  const result = {};
  for (const member of state.group.members) {
    const box = $(`participant-${member.id}`);
    if (!box) continue;
    const input = $(`value-${member.id}`);
    result[member.id] = { checked: box.checked, value: input ? input.value : "" };
  }
  return result;
}

function renderExpenses() {
  const items = state.expenses.map((expense) => {
    const info = el(
      "div",
      {},
      el("strong", {}, expense.description),
      el("br"),
      el(
        "span",
        { class: "muted small" },
        `${memberName(expense.payer_id)} paid ${formatMoney(expense.amount)} (${expense.split_type.toLowerCase()})`
      )
    );
    const edit = el("button", { type: "button", class: "secondary small-btn" }, "Edit");
    edit.addEventListener("click", guard(() => startEdit(expense)));
    const remove = el("button", { type: "button", class: "danger small-btn" }, "Delete");
    remove.addEventListener("click", guard(() => deleteExpense(expense)));
    return el("li", {}, info, el("div", { class: "actions" }, edit, remove));
  });
  $("expense-list").replaceChildren(...items);
  $("no-expenses").hidden = state.expenses.length > 0;
}

function renderBalances() {
  const rows = state.group.members.map((member) => {
    const cents = state.balances[member.id] || 0;
    const cls = cents > 0 ? "positive" : cents < 0 ? "negative" : "";
    const sign = cents > 0 ? "+" : "";
    return el(
      "tr",
      {},
      el("td", {}, member.name),
      el("td", { class: `num ${cls}` }, sign + formatMoney(cents))
    );
  });
  document.querySelector("#balances-table tbody").replaceChildren(...rows);
}

function renderPlan() {
  const items = state.plan.map((payment) => {
    const text = `${memberName(payment.from)} pays ${memberName(payment.to)} ${formatMoney(payment.amount)}`;
    const record = el("button", { type: "button", class: "small-btn" }, "Record payment");
    record.addEventListener("click", guard(() => recordPayment(payment)));
    return el("li", {}, el("span", {}, text), record);
  });
  $("plan-list").replaceChildren(...items);
  $("no-plan").hidden = state.plan.length > 0;
}

/* ---------------------------------------------------------------- actions */
async function createGroup() {
  const input = $("group-name");
  const group = await api("POST", "/groups", { name: input.value });
  input.value = "";
  await loadGroups();
  await selectGroup(group.id);
  showMessage(`Group "${group.name}" created.`, true);
}

async function deleteGroup() {
  if (!state.group) return;
  if (!confirm(`Delete the group "${state.group.name}" and all its data?`)) return;
  await api("DELETE", `/groups/${state.groupId}`);
  state.groupId = null;
  state.group = null;
  setEditMode(null);
  await loadGroups();
  renderGroupView();
  showMessage("Group deleted.", true);
}

async function addMember() {
  const input = $("member-name");
  await api("POST", `/groups/${state.groupId}/members`, { name: input.value });
  input.value = "";
  await loadGroup();
}

async function removeMember(member) {
  await api("DELETE", `/groups/${state.groupId}/members/${member.id}`);
  await loadGroup();
}

function setEditMode(expenseId) {
  state.editingId = expenseId;
  $("expense-form-title").textContent = expenseId ? "Edit expense" : "Add an expense";
  $("expense-submit").textContent = expenseId ? "Save changes" : "Add expense";
  $("expense-cancel").hidden = !expenseId;
}

function cancelEdit() {
  setEditMode(null);
  $("expense-form").reset();
  renderExpenseForm(true);
}

/* Build the request body from the form, checking everything the server checks too,
 * so the person gets a clear message before anything is sent. */
function buildExpenseBody() {
  const members = state.group.members;
  if (members.length === 0) throw new Error("Add some members first.");

  const description = $("expense-description").value.trim();
  if (!description) throw new Error("Please enter a description.");

  const amount = parseMoney($("expense-amount").value);
  if (amount === null || amount <= 0) throw new Error("Enter a valid amount, such as 12.50.");

  const split = $("expense-split").value;
  const chosen = members.filter((m) => $(`participant-${m.id}`).checked);
  if (chosen.length === 0) throw new Error("Select at least one person to split between.");

  const body = {
    description,
    amount,
    payer_id: Number($("expense-payer").value),
    split_type: split,
  };

  if (split === "EQUAL") {
    body.participants = chosen.map((m) => m.id);
    return body;
  }

  const values = {};
  let total = 0;
  for (const member of chosen) {
    const text = $(`value-${member.id}`).value;
    const parsed = parseMoney(text);
    if (parsed === null) throw new Error(`Enter a valid number for ${member.name}.`);
    values[member.id] = split === "PERCENT" ? text.trim() : parsed;
    total += parsed;
  }
  if (split === "EXACT" && total !== amount) {
    throw new Error(`The amounts add up to ${formatMoney(total)} but the expense is ${formatMoney(amount)}.`);
  }
  if (split === "PERCENT" && total !== 10000) {
    throw new Error(`The percentages add up to ${formatMoney(total)}%, they must add up to 100.`);
  }
  body[split === "EXACT" ? "shares" : "percents"] = values;
  return body;
}

async function submitExpense() {
  const body = buildExpenseBody();
  const editing = state.editingId;
  if (editing) {
    await api("PUT", `/groups/${state.groupId}/expenses/${editing}`, body);
  } else {
    await api("POST", `/groups/${state.groupId}/expenses`, body);
  }
  setEditMode(null);
  $("expense-form").reset();
  await loadGroup();
  renderExpenseForm(true);
  showMessage(editing ? "Expense updated." : "Expense added.", true);
}

/* Fill the form with an existing expense. The server stores cents, not the percentages
 * that were typed, so a PERCENT expense is edited as exact amounts. */
function startEdit(expense) {
  setEditMode(expense.id);
  const split = expense.split_type === "EQUAL" ? "EQUAL" : "EXACT";
  $("expense-description").value = expense.description;
  $("expense-amount").value = formatMoney(expense.amount);
  $("expense-payer").value = String(expense.payer_id);
  $("expense-split").value = split;

  const previous = {};
  for (const member of state.group.members) {
    const share = expense.shares[member.id];
    previous[member.id] = {
      checked: share !== undefined,
      value: split === "EXACT" && share !== undefined ? formatMoney(share) : "",
    };
  }
  renderParticipants(previous);
  if (expense.split_type === "PERCENT") {
    showMessage("Percentage expenses are edited as exact amounts.", true);
  }
  $("expense-form").scrollIntoView({ behavior: "smooth" });
}

async function deleteExpense(expense) {
  if (!confirm(`Delete "${expense.description}"?`)) return;
  await api("DELETE", `/groups/${state.groupId}/expenses/${expense.id}`);
  if (state.editingId === expense.id) cancelEdit();
  await loadGroup();
}

async function recordPayment(payment) {
  await api("POST", `/groups/${state.groupId}/settlements`, {
    from_member: payment.from,
    to_member: payment.to,
    amount: payment.amount,
  });
  await loadGroup();
  showMessage("Payment recorded.", true);
}

/* ------------------------------------------------------------------ start */
document.addEventListener("DOMContentLoaded", () => {
  $("group-form").addEventListener("submit", guard(createGroup));
  $("member-form").addEventListener("submit", guard(addMember));
  $("expense-form").addEventListener("submit", guard(submitExpense));
  $("expense-cancel").addEventListener("click", guard(cancelEdit));
  $("delete-group").addEventListener("click", guard(deleteGroup));
  $("expense-split").addEventListener("change", () => {
    if (!state.group) return;
    const previous = readParticipants();
    for (const id of Object.keys(previous)) previous[id].value = "";
    renderParticipants(previous);
  });
  guard(loadGroups)();
});
