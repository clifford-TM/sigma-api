document.addEventListener("DOMContentLoaded", () => {
  configurarEventos();
  configurarConfirmacoes();
  configurarEnvioDeFormularioLista();
});

function configurarEventos() {
  const botoesIniciar = document.querySelectorAll('[data-action="iniciar-evento"]');
  const botoesEncerrar = document.querySelectorAll('[data-action="encerrar-evento"]');

  botoesIniciar.forEach((botao) => {
    botao.addEventListener("click", () => {
      iniciarEvento(botao.dataset.eventoId);
    });
  });

  botoesEncerrar.forEach((botao) => {
    botao.addEventListener("click", () => {
      encerrarEvento(botao.dataset.eventoId);
    });
  });
}

async function iniciarEvento(eventoId) {
  try {
    const resposta = await fetch(`/eventos/${eventoId}/iniciar`, {
      method: "POST"
    });

    if (resposta.ok || resposta.redirected) {
      alert("Pedido de início enviado.\n\nAproxime a tag do responsável no leitor RFID.");
      location.reload();
      return;
    }

    const dados = await resposta.json();
    alert("Erro ao iniciar evento: " + (dados.detail || "erro desconhecido"));
  } catch (erro) {
    console.error(erro);
    alert("Falha ao comunicar com o servidor.");
  }
}

async function encerrarEvento(eventoId) {
  try {
    const resposta = await fetch(`/eventos/${eventoId}/disparar-fim`, {
      method: "POST"
    });

    const dados = await resposta.json();

    if (resposta.ok) {
      alert("Pedido de encerramento enviado.\n\nAproxime novamente a tag do responsável no leitor RFID.");
      location.reload();
      return;
    }

    alert("Erro ao encerrar evento: " + (dados.detail || "erro desconhecido"));
  } catch (erro) {
    console.error(erro);
    alert("Falha ao comunicar com o servidor.");
  }
}

function configurarConfirmacoes() {
  const elementos = document.querySelectorAll("[data-confirm]");

  elementos.forEach((elemento) => {
    elemento.addEventListener("click", (event) => {
      const mensagem =
        elemento.dataset.confirm || "Deseja continuar?";

      if (!confirm(mensagem)) {
        event.preventDefault();
        event.stopPropagation();
      }
    });
  });
}

function configurarEnvioDeFormularioLista() {
  const forms = document.querySelectorAll("form");

  forms.forEach((form) => {
    form.addEventListener("submit", () => {
      const submitButton = form.querySelector(
        'button[type="submit"]'
      );

      if (!submitButton) {
        return;
      }

      submitButton.disabled = true;

      if (submitButton.textContent.trim()) {
        submitButton.dataset.originalText =
          submitButton.textContent;

        submitButton.textContent = "Processando...";
      }
    });
  });
}