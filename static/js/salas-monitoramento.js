document.addEventListener("DOMContentLoaded", () => {
  configurarConfirmacoesDeContingencia();
  atualizarSalas();

  setInterval(atualizarSalas, 5000);
});

function configurarConfirmacoesDeContingencia() {
  const elementos = document.querySelectorAll("[data-confirm]");

  elementos.forEach((elemento) => {
    elemento.addEventListener("click", (event) => {
      const mensagem = elemento.dataset.confirm || "Deseja continuar?";

      if (!confirm(mensagem)) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
  });
}

function atualizarTextoPorta(elemento, portaAberta) {
  elemento.classList.remove(
    "porta-aberta",
    "porta-fechada",
    "porta-sem-leitura"
  );

  const card = elemento.closest(".room-door");

  if (card) {
    card.classList.remove(
      "porta-aberta",
      "porta-fechada",
      "porta-sem-leitura"
    );
  }

  if (portaAberta === null) {
    elemento.innerText = "Porta sem leitura";
    elemento.classList.add("porta-sem-leitura");

    if (card) card.classList.add("porta-sem-leitura");
    return;
  }

  if (portaAberta) {
    elemento.innerText = "Porta aberta";
    elemento.classList.add("porta-aberta");

    if (card) card.classList.add("porta-aberta");
    return;
  }

  elemento.innerText = "Porta fechada";
  elemento.classList.add("porta-fechada");

  if (card) card.classList.add("porta-fechada");
}

async function atualizarSalas() {
  try {
    const response = await fetch("/seguranca/api/salas/status");

    if (!response.ok) {
      console.error("Erro HTTP ao atualizar salas:", response.status);
      return;
    }

    const data = await response.json();

    data.forEach((sala) => {
      const portaEl = document.getElementById(`porta-${sala.sala_id}`);

      if (portaEl) {
        atualizarTextoPorta(portaEl, sala.porta_aberta);
      }

      const statusEl = document.getElementById(`status-${sala.sala_id}`);

      if (statusEl) {
        statusEl.innerText = sala.status_visual;
      }

      const card = document.getElementById(`sala-${sala.sala_id}`);

      if (card) {
        card.classList.remove("livre", "ocupada", "inspecao", "problema");

        if (sala.nivel === "livre") {
          card.classList.add("livre");
        } else if (sala.nivel === "ocupada") {
          card.classList.add("ocupada");
        } else if (sala.nivel === "inspecao") {
          card.classList.add("inspecao");
        } else {
          card.classList.add("problema");
        }
      }
    });
  } catch (err) {
    console.error("Erro ao atualizar salas:", err);
  }
}