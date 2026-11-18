// Painel do gestor de anúncios: lê a API JSON e monta placar, tabela, detalhe e alertas.
// Todo texto vindo da API entra via textContent (nunca innerHTML).
"use strict";

const estado = { resumo: null, veiculos: [], filtro: { situacao: "", plataforma: "", marca: "", q: "" }, placa: null };
// Contadores de requisição: uma resposta antiga que chega depois da mais nova é descartada.
const pedidos = { lista: 0, detalhe: 0 };
const CORES_PLATAFORMA = ["var(--divergente)", "var(--parado)", "var(--nao-converte)", "var(--bem)"];

// Ordem e textos do placar. "vendido" aparece como "Remover", que é a ação pedida.
const PLACAR = [
  ["vendido", "Remover (já vendido)"],
  ["fora_do_ar", "Fora do ar"],
  ["nao_converte", "Atrai mas não converte"],
  ["parado", "Parados"],
  ["preco_alto", "Acima da referência"],
  ["divergente", "Preço divergente"],
  ["preco_baixo", "Abaixo da referência"],
  ["bem", "Performando bem"],
  ["novo", "Novos"],
];

const real = new Intl.NumberFormat("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const inteiro = new Intl.NumberFormat("pt-BR");
const compacto = new Intl.NumberFormat("pt-BR", { notation: "compact", maximumFractionDigits: 1 });
const $ = (id) => document.getElementById(id);

function el(tag, attrs = {}, ...filhos) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const f of filhos.flat()) {
    if (f === null || f === undefined || f === false) continue;
    n.append(f instanceof Node ? f : document.createTextNode(String(f)));
  }
  return n;
}

function svg(tag, attrs = {}, texto) {
  const n = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  if (texto !== undefined) n.textContent = texto;
  return n;
}

const dataHora = (iso) => (iso ? new Date(iso).toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" }) : "—");
const dataCurta = (iso) => new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
const nomeVeiculo = (v) => `${v.marca} ${v.modelo} ${v.versao} ${v.ano}`;

function placa(p, grande = false) {
  const antiga = /^[A-Z]{3}\d{4}$/.test(p);
  return el("span", { class: `placa${antiga ? " antiga" : ""}${grande ? " grande" : ""}`, title: antiga ? "Placa modelo antigo" : "Placa Mercosul" },
    el("span", {}, antiga ? `${p.slice(0, 3)}-${p.slice(3)}` : p));
}

async function api(caminho, opcoes) {
  const r = await fetch(caminho, opcoes);
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `erro ${r.status}`);
  return r.json();
}

// ---------- Placar e filtros ----------
function montarPlacar() {
  const r = estado.resumo;
  const nav = $("placar");
  nav.replaceChildren();
  const botao = (sit, texto, n, extra = "") =>
    el("button", {
      type: "button", "data-sit": sit || null, class: extra || null,
      "aria-pressed": String(estado.filtro.situacao === sit),
      disabled: Boolean(sit) && n === 0 && estado.filtro.situacao !== sit,
      onclick: () => { estado.filtro.situacao = estado.filtro.situacao === sit ? "" : sit; atualizarLista(); },
    }, el("b", {}, inteiro.format(n)), texto);

  nav.append(botao("", "Todos", r.total));
  for (const [sit, texto] of PLACAR) {
    const n = r.por_filtro[sit];
    if (sit === "fora_do_ar" && n === 0) continue;
    nav.append(botao(sit, texto, n, sit === "vendido" && n > 0 ? "urgente" : ""));
  }
  $("placar-resumo").textContent = r.total
    ? `${r.ativos} carros à venda, anunciados há ${r.media_dias} dias em média. ` +
      `${real.format(r.valor_parado)} em carros parados ou que não convertem.`
    : "";
}

function preencherSelect(id, valores) {
  const s = $(id);
  const atual = s.value;
  s.replaceChildren(el("option", { value: "" }, "Todas"), ...valores.map((v) => el("option", { value: v }, v)));
  s.value = valores.includes(atual) ? atual : "";
}

async function carregarResumo() {
  estado.resumo = await api("/api/resumo");
  const r = estado.resumo;
  $("ultima-coleta").textContent = r.ultima_coleta ? `Última coleta: ${dataHora(r.ultima_coleta)}` : "Nenhuma coleta ainda";
  $("etiqueta-demo").hidden = !r.demo;
  $("coletar").hidden = r.somente_leitura;
  preencherSelect("filtro-plataforma", r.plataformas);
  preencherSelect("filtro-marca", r.marcas);
  montarPlacar();
}

// ---------- Tabela ----------
function celulaPreco(v) {
  const td = el("td", { class: "num", "data-rotulo": "Preço" });
  if (v.preco_atual === null) { td.append("—"); return td; }
  td.append(el("span", { class: "preco" }, real.format(v.preco_atual)));
  if (v.referencia) {
    const d = v.diferenca_ref;
    const cfg = estado.resumo.config;
    const classe = d > cfg.acima_ref ? "ref acima" : d < -cfg.abaixo_ref ? "ref abaixo" : "ref";
    const sinal = d > 0 ? "+" : "";
    td.append(el("span", { class: classe }, `${v.origem_referencia === "FIPE" ? "FIPE" : "Mediana"} ${sinal}${Math.round(d * 100)}%`));
  } else {
    td.append(el("span", { class: "ref" }, "sem referência"));
  }
  return td;
}

function celulaSituacao(v) {
  const rotulos = estado.resumo.rotulos;
  const td = el("td", { "data-sit": v.situacao }, el("span", { class: "situacao" }, rotulos[v.situacao]));
  if (v.sinais.length) td.append(el("span", { class: "sinais" }, "Também: " + v.sinais.map((s) => rotulos[s].toLowerCase()).join(", ")));
  if (v.remover_de.length) td.append(el("span", { class: "remover-de" }, `Remover de ${v.remover_de.join(", ")}`));
  if (v.sugestao) td.append(el("span", { class: "sugestao", title: "Preço sugerido" }, `Sugestão ${real.format(v.sugestao)}`));
  return td;
}

function linha(v) {
  const plataformas = v.plataformas.map((p) =>
    el("span", { class: `plataforma${v.remover_de.includes(p) ? " remover" : ""}` }, p));
  const tr = el("tr", {
    tabindex: "0", "aria-selected": String(estado.placa === v.placa), "data-placa": v.placa,
    onclick: () => abrirDetalhe(v.placa),
    onkeydown: (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); abrirDetalhe(v.placa); } },
  },
    el("td", {}, el("div", { class: "veiculo-nome" }, nomeVeiculo(v)),
      el("div", { class: "veiculo-linha2" }, placa(v.placa), plataformas)),
    celulaPreco(v),
    el("td", { class: "num", "data-rotulo": "Dias anunciado" }, v.dias_anunciado),
    el("td", { class: "num", "data-rotulo": "Contatos em 7 dias" }, `${v.contatos_janela}`,
      el("span", { class: "ref" }, `${inteiro.format(v.visitas_janela)} visitas`)),
    celulaSituacao(v),
  );
  return tr;
}

async function atualizarLista() {
  const f = estado.filtro;
  const params = new URLSearchParams(Object.entries(f).filter(([, v]) => v));
  const meu = ++pedidos.lista;
  const { veiculos } = await api(`/api/veiculos?${params}`);
  if (meu !== pedidos.lista) return;  // chegou outra busca depois desta
  estado.veiculos = veiculos;
  $("linhas").replaceChildren(...veiculos.map(linha));
  const vazio = $("vazio");
  vazio.hidden = veiculos.length > 0;
  vazio.textContent = estado.resumo.total
    ? "Nenhum veículo com esses filtros. Limpe a busca ou escolha outra situação."
    : "O banco ainda não tem coletas. Clique em Coletar agora ou rode python src/cli.py demo.";
  $("filtros-total").textContent = `${veiculos.length} de ${estado.resumo.total} veículos`;
  montarPlacar();
}

// ---------- Detalhe ----------
function grafico(historico, referencia) {
  const L = 360, A = 220, m = { e: 54, d: 20, t: 10, b: 24 }, faixaBarras = 46, respiro = 16;
  const plataformas = [...new Set(historico.flatMap((h) => Object.keys(h.precos)))].sort();
  const precos = historico.flatMap((h) => Object.values(h.precos));
  if (referencia) precos.push(referencia);
  const n = historico.length;
  const s = svg("svg", { viewBox: `0 0 ${L} ${A}`, class: "grafico", role: "img",
    "aria-label": "Preço por plataforma, referência e contatos por coleta" });
  if (!n) return { svg: s, plataformas };

  let min = Math.min(...precos), max = Math.max(...precos);
  if (min === max) { min *= 0.95; max *= 1.05; }
  const folga = (max - min) * 0.12;
  min -= folga; max += folga;
  const altoPreco = A - m.t - m.b - faixaBarras - respiro;
  const x = (i) => m.e + (n === 1 ? (L - m.e - m.d) / 2 : (i * (L - m.e - m.d)) / (n - 1));
  const y = (v) => m.t + ((max - v) / (max - min)) * altoPreco;

  for (let k = 0; k <= 3; k++) {
    const v = min + ((max - min) * k) / 3;
    s.append(svg("line", { class: "grade", x1: m.e, x2: L - m.d, y1: y(v), y2: y(v) }));
    s.append(svg("text", { x: m.e - 6, y: y(v) + 4, "text-anchor": "end" }, compacto.format(v)));
  }
  if (referencia) s.append(svg("line", { class: "ref-linha", x1: m.e, x2: L - m.d, y1: y(referencia), y2: y(referencia) }));

  // Barras de contatos por coleta, na faixa de baixo.
  const maxContatos = Math.max(1, ...historico.map((h) => h.contatos));
  const baseBarras = A - m.b;
  const largura = Math.max(6, Math.min(18, (L - m.e - m.d) / n - 6));
  historico.forEach((h, i) => {
    const alt = (h.contatos / maxContatos) * (faixaBarras - 8);
    s.append(svg("rect", { class: "barra", x: x(i) - largura / 2, y: baseBarras - alt, width: largura, height: Math.max(alt, 0.5) }));
    if (i === 0 || i === n - 1 || n <= 6 || i % 2 === 0) {
      s.append(svg("text", { x: x(i), y: A - 6, "text-anchor": "middle" }, dataCurta(h.coletado_em)));
    }
  });
  s.append(svg("text", { x: m.e - 6, y: baseBarras - faixaBarras + 14, "text-anchor": "end" }, "contatos"));

  plataformas.forEach((p, idx) => {
    const cor = CORES_PLATAFORMA[idx % CORES_PLATAFORMA.length];
    const pontos = historico.map((h, i) => (p in h.precos ? [x(i), y(h.precos[p])] : null));
    let trecho = [];
    const fechar = () => {
      if (trecho.length > 1) s.append(svg("polyline", { points: trecho.map((q) => q.join(",")).join(" "), fill: "none", stroke: cor, "stroke-width": 2.2, "stroke-linejoin": "round" }));
      trecho = [];
    };
    pontos.forEach((q) => { if (q) { trecho.push(q); s.append(svg("circle", { cx: q[0], cy: q[1], r: 2.6, fill: cor })); } else fechar(); });
    fechar();
  });
  return { svg: s, plataformas };
}

async function abrirDetalhe(p) {
  estado.placa = p;
  document.querySelectorAll("#linhas tr").forEach((tr) => tr.setAttribute("aria-selected", String(tr.dataset.placa === p)));
  try { history.replaceState(null, "", `?placa=${encodeURIComponent(p)}`); } catch (_) { /* sem history: segue */ }
  const caixa = $("detalhe");
  const meu = ++pedidos.detalhe;
  let dados;
  try {
    dados = await api(`/api/veiculos/${encodeURIComponent(p)}`);
  } catch (erro) {
    if (meu === pedidos.detalhe) caixa.replaceChildren(el("p", { class: "detalhe-dica" }, `Não foi possível abrir ${p}: ${erro.message}.`));
    return;
  }
  if (meu !== pedidos.detalhe) return;  // o usuário já clicou em outro veículo
  const v = dados.veiculo;
  const g = grafico(dados.historico, v.referencia);
  const legenda = el("div", { class: "legenda" },
    g.plataformas.map((nome, i) => el("span", {}, el("i", { style: `background:${CORES_PLATAFORMA[i % CORES_PLATAFORMA.length]}` }), nome)),
    v.referencia ? el("span", {}, el("i", { class: "tracejado" }), `Referência ${v.origem_referencia === "FIPE" ? "FIPE" : "(mediana)"} ajustada pela km`) : null,
    el("span", {}, el("i", { class: "bloco" }), "Contatos novos desde a coleta anterior"));

  const numeros = el("dl", { class: "detalhe-numeros" },
    el("div", {}, el("dt", {}, "Preço"), el("dd", {}, v.preco_atual ? real.format(v.preco_atual) : "—")),
    el("div", {}, el("dt", {}, "Referência"), el("dd", {}, v.referencia ? real.format(v.referencia) : "—")),
    el("div", {}, el("dt", {}, "Sugestão"), el("dd", {}, v.sugestao ? el("span", { class: "sugestao" }, real.format(v.sugestao)) : "—")));

  const anuncios = el("ul", { class: "anuncios" }, dados.anuncios.map((a) =>
    el("li", {}, el("span", {}, a.plataforma),
      el("span", {}, a.status === "ativo" && v.remover_de.includes(a.plataforma) ? "ativo, remover" : a.status,
        a.preco ? `, ${real.format(a.preco)}` : ""))));

  caixa.replaceChildren(el("div", { class: "detalhe-conteudo" },
    el("div", { class: "detalhe-cabeca" }, placa(v.placa, true),
      el("div", {}, el("h2", {}, `${v.marca} ${v.modelo}`), el("p", {}, `${v.versao}, ${v.ano}, ${inteiro.format(v.km)} km`))),
    el("p", { "data-sit": v.situacao }, el("span", { class: "situacao" }, estado.resumo.rotulos[v.situacao])),
    el("p", { class: "detalhe-motivo" }, v.motivo),
    numeros, g.svg, legenda,
    el("h3", {}, "Anúncios"), anuncios));
}

// ---------- Alertas, coleta e tema ----------
async function carregarAlertas() {
  const { alertas } = await api("/api/alertas?limite=40");
  $("lista-alertas").replaceChildren(...(alertas.length ? alertas.map((a) =>
    el("li", {}, el("time", { datetime: a.quando }, dataHora(a.quando)), el("span", {}, a.placa), el("span", {}, a.mensagem)))
    : [el("li", {}, "Nenhum alerta registrado.")]));
}

async function coletarAgora() {
  const b = $("coletar");
  b.disabled = true; b.textContent = "Coletando…";
  try {
    const r = await api("/api/coletar", { method: "POST" });
    b.textContent = `Coletado: ${r.alertas} alerta(s) novo(s)`;
    await recarregar();
  } catch (erro) {
    b.textContent = `Falhou: ${erro.message}`;
  } finally {
    setTimeout(() => { b.disabled = false; b.textContent = "Coletar agora"; }, 2500);
  }
}

const TEMAS = ["automático", "claro", "escuro"];
function aplicarTema(t) {
  if (t === "automático") document.documentElement.removeAttribute("data-tema");
  else document.documentElement.dataset.tema = t;
  $("tema").textContent = `Tema: ${t}`;
}
function trocarTema() {
  let atual = "automático";
  try { atual = localStorage.getItem("tema") || "automático"; } catch (_) { /* sem storage */ }
  const prox = TEMAS[(TEMAS.indexOf(atual) + 1) % TEMAS.length];
  try { localStorage.setItem("tema", prox); } catch (_) { /* sem storage */ }
  aplicarTema(prox);
}

async function recarregar() {
  await carregarResumo();
  await atualizarLista();
  await carregarAlertas();
  if (estado.placa) await abrirDetalhe(estado.placa);
}

function iniciar() {
  try { aplicarTema(localStorage.getItem("tema") || "automático"); } catch (_) { aplicarTema("automático"); }
  $("tema").addEventListener("click", trocarTema);
  $("coletar").addEventListener("click", coletarAgora);
  $("filtro-plataforma").addEventListener("change", (e) => { estado.filtro.plataforma = e.target.value; atualizarLista(); });
  $("filtro-marca").addEventListener("change", (e) => { estado.filtro.marca = e.target.value; atualizarLista(); });
  let espera;
  $("filtro-q").addEventListener("input", (e) => {
    clearTimeout(espera);
    espera = setTimeout(() => { estado.filtro.q = e.target.value.trim(); atualizarLista(); }, 200);
  });
  const inicial = new URLSearchParams(location.search).get("placa");
  recarregar().then(() => {
    const alvo = inicial || (estado.veiculos[0] && estado.veiculos[0].placa);
    if (alvo) abrirDetalhe(alvo);
  }).catch((erro) => { $("ultima-coleta").textContent = `Não foi possível carregar o painel: ${erro.message}`; });
}

iniciar();
