// Painel do rastreador de preços. Todo texto vindo da API entra via textContent.
const $ = (id) => document.getElementById(id);
const NS = "http://www.w3.org/2000/svg";

function el(tag, props = {}, ...filhos) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(props)) {
    if (k === "class") e.className = v; else if (k === "text") e.textContent = v; else e.setAttribute(k, v);
  }
  e.append(...filhos);
  return e;
}
function svg(tag, attrs = {}, texto) {
  const e = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) e.setAttribute(k, v);
  if (texto !== undefined) e.textContent = texto;
  return e;
}

const libra = (n) => "£" + Number(n).toFixed(2);
const dataHora = (iso) => new Date(iso).toLocaleString("pt-BR", { day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" });
const dataCurta = (iso) => new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });

let toastTimer;
function avisar(texto) {
  const t = $("toast");
  t.textContent = texto;
  t.classList.add("visivel");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove("visivel"), 3200);
}

// ---- Tema (automático, claro, escuro); aceita ?tema=claro|escuro ----------
const TEMAS = [["auto", "Tema automático"], ["light", "Tema claro"], ["dark", "Tema escuro"]];
function temaSalvo() {
  const p = new URLSearchParams(location.search).get("tema");
  if (p === "claro") return "light";
  if (p === "escuro") return "dark";
  try { return localStorage.getItem("tema") || "auto"; } catch (_) { return "auto"; }
}
function aplicarTema(chave) {
  if (chave === "auto") document.documentElement.removeAttribute("data-theme");
  else document.documentElement.setAttribute("data-theme", chave);
  $("tema").textContent = TEMAS.find((t) => t[0] === chave)[1];
}

// ---- Estado ----------------------------------------------------------------
let produtos = [];
let selecionado = null;
let detalhe = null;
let limite = null;

function variacao(p) {
  const d = p.preco - p.preco_inicial;
  if (Math.abs(d) < 0.005) return { texto: "sem variação", classe: "" };
  return { texto: `${d > 0 ? "+" : "-"}${libra(Math.abs(d))} desde a 1ª coleta`, classe: d < 0 ? "var-queda" : "var-alta" };
}

function desenharLista() {
  const termo = $("busca").value.trim().toLowerCase();
  const caixa = $("lista");
  caixa.replaceChildren();
  const visiveis = produtos.filter((p) => p.nome.toLowerCase().includes(termo));
  $("contagem").textContent = `${visiveis.length} de ${produtos.length}`;
  if (!produtos.length) {
    caixa.append(el("p", { class: "vazio", text: "Nenhum produto no banco ainda. Clique em Coletar agora para buscar os preços." }));
    return;
  }
  if (!visiveis.length) {
    caixa.append(el("p", { class: "vazio", text: "Nenhum produto com esse nome. Tente outro termo." }));
    return;
  }
  for (const p of visiveis) {
    const v = variacao(p);
    const b = el("button", { class: "item", type: "button", "aria-current": String(p.id === selecionado) },
      el("span", { class: "nome", title: p.nome, text: p.nome }),
      el("span", { class: "preco", text: libra(p.preco) }),
      el("span", { class: "meta" }, el("span", { class: v.classe, text: v.texto }), el("span", { text: `${p.coletas} coleta${p.coletas === 1 ? "" : "s"}` }))
    );
    b.addEventListener("click", () => escolher(p.id));
    caixa.append(b);
  }
  const atual = caixa.querySelector('[aria-current="true"]');
  if (atual) {
    // Rola só a lista (scrollIntoView arrastaria a página inteira em telas pequenas).
    const r = atual.getBoundingClientRect(), c = caixa.getBoundingClientRect();
    if (r.top < c.top || r.bottom > c.bottom) caixa.scrollTop += r.top - c.top - (c.height - r.height) / 2;
  }
}

async function escolher(id) {
  selecionado = id;
  desenharLista();
  const resp = await fetch(`/api/produto/${encodeURIComponent(id)}`);
  if (!resp.ok) { avisar("Não foi possível carregar o produto."); return; }
  detalhe = await resp.json();
  desenharDetalhe();
}

function desenharDetalhe() {
  const d = detalhe;
  if (!d) return;
  const r = d.resumo;
  $("vazio-detalhe").hidden = true;
  $("detalhe").hidden = false;
  $("nome").textContent = d.nome;
  $("link").href = d.url;
  const abaixo = limite !== null && r.preco_atual < limite;
  $("preco").textContent = libra(r.preco_atual);
  $("preco").className = "preco-grande" + (abaixo ? " abaixo" : "");
  $("situacao").textContent = abaixo
    ? `Abaixo do limite de ${libra(limite)}: gera alerta a cada coleta.`
    : limite !== null ? `Acima do limite de ${libra(limite)}.` : "Defina um limite abaixo do gráfico para acompanhar alertas.";

  const q = r.maior_queda;
  $("n-menor").textContent = libra(r.menor_preco);
  $("d-menor").textContent = dataCurta(r.menor_preco_em);
  $("n-maior").textContent = libra(r.maior_preco);
  $("d-maior").textContent = dataCurta(r.maior_preco_em);
  $("n-medio").textContent = libra(r.preco_medio);
  $("d-medio").textContent = `${r.coletas} coleta${r.coletas === 1 ? "" : "s"}`;
  $("n-queda").textContent = q.em ? `-${libra(q.valor)}` : "nenhuma";
  $("d-queda").textContent = q.em ? `${q.percentual}% em ${dataCurta(q.em)}` : "sem queda registrada";
  desenharGrafico();
}

function desenharGrafico() {
  const pts = detalhe.pontos.map((p) => ({ t: new Date(p.coletado_em).getTime(), v: p.preco, iso: p.coletado_em }));
  const L = 880, A = 340, m = { e: 72, d: 24, c: 24, b: 44 };
  const g = svg("svg", { viewBox: `0 0 ${L} ${A}`, class: "grafico", role: "img", "aria-label": `Gráfico de preço de ${detalhe.nome}` });
  const valores = pts.map((p) => p.v).concat(limite !== null ? [limite] : []);
  let min = Math.min(...valores), max = Math.max(...valores);
  if (max - min < 1) { min -= 1; max += 1; }
  const folga = (max - min) * 0.12; min -= folga; max += folga;
  const t0 = pts[0].t, t1 = pts[pts.length - 1].t;
  const x = (t) => (t1 === t0 ? (m.e + L - m.d) / 2 : m.e + ((t - t0) / (t1 - t0)) * (L - m.e - m.d));
  const y = (v) => m.c + (1 - (v - min) / (max - min)) * (A - m.c - m.b);

  for (let i = 0; i <= 4; i++) {
    const v = min + ((max - min) * i) / 4, yy = y(v);
    g.append(svg("line", { x1: m.e, x2: L - m.d, y1: yy, y2: yy, class: "grade" }), svg("text", { x: m.e - 8, y: yy + 4, "text-anchor": "end" }, libra(v)));
  }
  if (limite !== null) {
    const yl = y(limite);
    g.append(svg("rect", { x: m.e, y: yl, width: L - m.e - m.d, height: Math.max(0, A - m.b - yl), class: "zona" }),
      svg("line", { x1: m.e, x2: L - m.d, y1: yl, y2: yl, class: "limite" }),
      svg("text", { x: L - m.d, y: yl - 6, "text-anchor": "end", class: "rotulo-limite" }, `limite ${libra(limite)}`));
  }
  g.append(svg("path", { class: "linha", d: pts.map((p, i) => `${i ? "L" : "M"}${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ") }));
  for (const p of pts) {
    const c = svg("circle", { cx: x(p.t), cy: y(p.v), r: 4.5, class: "ponto" + (limite !== null && p.v < limite ? " abaixo" : "") });
    c.append(svg("title", {}, `${dataHora(p.iso)}: ${libra(p.v)}`));
    g.append(c);
  }
  // Rótulo do menor preço: abaixo do ponto, ou acima se ele estiver perto do rodapé do gráfico.
  const menor = pts.reduce((a, b) => (b.v < a.v ? b : a));
  const perto = y(menor.v) > A - m.b - 34;
  const xm = Math.min(Math.max(x(menor.t), m.e + 60), L - m.d - 60);
  g.append(svg("text", { x: xm, y: perto ? y(menor.v) - 14 : y(menor.v) + 22, "text-anchor": "middle", class: "minimo" }, `menor ${libra(menor.v)}`));
  // Datas do eixo: só as que cabem sem se sobrepor (coletas no mesmo dia viram uma marca).
  const marcas = [];
  for (const p of pts) {
    const ultima = marcas[marcas.length - 1];
    if (!ultima || (x(p.t) - x(ultima.t) >= 90 && dataCurta(p.iso) !== dataCurta(ultima.iso))) marcas.push(p);
  }
  for (const p of marcas) g.append(svg("text", { x: x(p.t), y: A - 12, "text-anchor": "middle" }, dataCurta(p.iso)));
  $("grafico").replaceChildren(g);
}

async function carregarAlertas() {
  const itens = await (await fetch("/api/alertas")).json();
  const caixa = $("alertas");
  caixa.replaceChildren();
  $("n-alertas").textContent = itens.length ? `${itens.length} recente${itens.length === 1 ? "" : "s"}` : "";
  if (!itens.length) {
    caixa.append(el("p", { class: "suave", text: "Nenhum alerta ainda. Eles aparecem quando uma coleta encontra preço abaixo do limite." }));
    return;
  }
  for (const a of itens.slice(0, 8)) {
    caixa.append(el("div", { class: "alerta" }, el("span", { class: "quando", text: dataHora(a.quando) }), el("span", { class: "msg", text: a.mensagem })));
  }
}

async function carregarProdutos(manterSelecao = true) {
  produtos = await (await fetch("/api/produtos")).json();
  const pedido = new URLSearchParams(location.search).get("produto"); // ?produto=<id> abre direto nele
  if (!manterSelecao && pedido && produtos.some((p) => p.id === pedido)) selecionado = pedido;
  else if (!manterSelecao || !produtos.some((p) => p.id === selecionado)) selecionado = produtos.length ? produtos[0].id : null;
  desenharLista();
  if (selecionado) await escolher(selecionado);
  else { $("detalhe").hidden = true; $("vazio-detalhe").hidden = false; }
}

async function coletar() {
  const botao = $("coletar"), erro = $("erro-coleta");
  erro.textContent = "";
  botao.disabled = true;
  botao.textContent = "Coletando…";
  try {
    const resp = await fetch("/api/coletar", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ limite }) });
    const r = await resp.json();
    if (!resp.ok) { erro.textContent = r.erro ? `Falha na coleta: ${r.erro}` : "Falha na coleta."; return; }
    avisar(`Coleta concluída: ${r.produtos} produtos salvos, ${r.alertas} alerta${r.alertas === 1 ? "" : "s"}.`);
    await Promise.all([carregarProdutos(), carregarAlertas()]);
  } catch (_) {
    erro.textContent = "Não foi possível falar com o servidor. Verifique se o comando servir está rodando.";
  } finally {
    botao.disabled = false;
    botao.textContent = "Coletar agora";
  }
}

async function iniciar() {
  let atual = temaSalvo();
  aplicarTema(atual);
  $("tema").addEventListener("click", () => {
    atual = TEMAS[(TEMAS.findIndex((t) => t[0] === atual) + 1) % TEMAS.length][0];
    try { localStorage.setItem("tema", atual); } catch (_) { /* vale só nesta visita */ }
    aplicarTema(atual);
  });
  const cfg = await (await fetch("/api/config")).json();
  limite = cfg.limite;
  if (cfg.demo) $("tag-demo").hidden = false;
  if (cfg.somente_leitura) {
    // Hospedagem pública: sem botão de coleta (evita visitantes acionarem o site de terceiros).
    $("bloco-coleta").hidden = true;
    $("nota-coleta").textContent =
      "Demonstração somente leitura: os preços são simulados a partir dos 20 livros reais da primeira página do catálogo, e a coleta no site real está desligada aqui. Para coletar de verdade, rode o projeto na sua máquina.";
  }
  $("limite").value = limite ?? "";
  $("limite").addEventListener("input", () => {
    const v = parseFloat($("limite").value.replace(",", "."));
    limite = Number.isFinite(v) && v > 0 ? v : null;
    if (detalhe) desenharDetalhe();
  });
  $("busca").addEventListener("input", desenharLista);
  $("coletar").addEventListener("click", coletar);
  await Promise.all([carregarProdutos(false), carregarAlertas()]);
}
iniciar().catch(() => { $("erro-coleta").textContent = "Não foi possível carregar os dados. Verifique se o servidor está rodando."; });
