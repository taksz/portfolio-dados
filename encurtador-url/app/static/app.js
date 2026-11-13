// Funções compartilhadas pelas páginas do encurtador.
// Todo texto vindo da API entra na página via textContent (nunca innerHTML).

function el(tag, props = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v;
    else if (k === "text") e.textContent = v;
    else e.setAttribute(k, v);
  }
  for (const f of filhos) e.append(f);
  return e;
}

// Tema: automático (segue o sistema), claro ou escuro. A escolha fica salva no navegador.
// Também aceita ?tema=claro ou ?tema=escuro na URL.
const TEMAS = [
  { chave: "auto", rotulo: "Tema automático" },
  { chave: "light", rotulo: "Tema claro" },
  { chave: "dark", rotulo: "Tema escuro" },
];

function temaSalvo() {
  const param = new URLSearchParams(location.search).get("tema");
  if (param === "claro") return "light";
  if (param === "escuro") return "dark";
  try { return localStorage.getItem("tema") || "auto"; } catch (_) { return "auto"; }
}

function aplicarTema(chave) {
  if (chave === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", chave);
  const botao = document.getElementById("tema");
  if (botao) botao.textContent = TEMAS.find((t) => t.chave === chave).rotulo;
}

document.addEventListener("DOMContentLoaded", () => {
  const nav = document.querySelector(".topo nav");
  if (!nav) return;
  let atual = temaSalvo();
  const botao = el("button", { id: "tema", class: "tema", type: "button", "aria-label": "Alternar tema" });
  nav.append(botao);
  aplicarTema(atual);
  botao.addEventListener("click", () => {
    atual = TEMAS[(TEMAS.findIndex((t) => t.chave === atual) + 1) % TEMAS.length].chave;
    try { localStorage.setItem("tema", atual); } catch (_) { /* sem armazenamento: vale só nesta visita */ }
    aplicarTema(atual);
  });
});

let toastTimer;
function avisar(mensagem) {
  let t = document.getElementById("toast");
  if (!t) {
    t = el("div", { id: "toast", class: "toast", role: "status" });
    document.body.append(t);
  }
  t.textContent = mensagem;
  t.classList.add("visivel");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("visivel"), 1800);
}

// Copia o texto e confirma no próprio botão ("Copiar link" vira "Link copiado" por 1,8 s).
async function copiar(texto, botao) {
  try {
    await navigator.clipboard.writeText(texto);
    avisar("Link copiado");
    if (botao) {
      const original = botao.dataset.rotulo || botao.textContent;
      botao.dataset.rotulo = original;
      botao.textContent = "Link copiado";
      setTimeout(() => { botao.textContent = original; }, 1800);
    }
  } catch (_) {
    avisar("Não foi possível copiar. Selecione o link e copie manualmente.");
  }
}

function formatarData(iso) {
  const d = new Date(iso);
  if (isNaN(d)) return iso;
  return d.toLocaleDateString("pt-BR");
}

function diaCurto(isoDia) {
  const [, m, d] = isoDia.split("-");
  return `${d}/${m}`;
}

// Lista de barras horizontais (rótulo, valor e trilho proporcional ao maior valor).
function listaBarras(container, dados, chaveRotulo, vazio) {
  container.replaceChildren();
  if (!dados.length) {
    container.append(el("p", { class: "suave", text: vazio }));
    return;
  }
  const max = Math.max(...dados.map((d) => d.cliques));
  for (const item of dados) {
    const pct = max > 0 ? (item.cliques / max) * 100 : 0;
    container.append(
      el(
        "div",
        { class: "item" },
        el(
          "div",
          { class: "topo-item" },
          el("span", { class: "nome", title: item[chaveRotulo], text: item[chaveRotulo] }),
          el("span", { class: "qtd", text: String(item.cliques) })
        ),
        el("div", { class: "trilho" }, el("div", { class: "preench", style: `width:${pct}%` }))
      )
    );
  }
}

// ---- Status dos links (ativo, expirado, desativado) ------------------------------------
function rotuloStatus(u) {
  if (u.status === "expirado") return "Expirado";
  if (u.status === "desativado") return "Desativado";
  return u.expira_em ? `Expira em ${formatarData(u.expira_em)}` : "Ativo";
}

// Ação principal de cada status: desativar um link ativo, reativar um desligado, renovar um vencido.
function acaoDoLink(u) {
  if (u.status === "desativado") return { texto: "Reativar", corpo: { ativo: true } };
  if (u.status === "expirado") return { texto: "Renovar por 30 dias", corpo: { expira_em_dias: 30 } };
  return { texto: "Desativar", corpo: { ativo: false } };
}

async function alterarLink(codigo, corpo) {
  const resp = await fetch(`/api/urls/${encodeURIComponent(codigo)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(corpo),
  });
  if (!resp.ok) throw new Error("Não foi possível alterar o link.");
  return resp.json();
}
