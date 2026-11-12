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

async function copiar(texto) {
  try {
    await navigator.clipboard.writeText(texto);
    avisar("Link copiado");
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
