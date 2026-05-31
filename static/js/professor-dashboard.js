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

document.addEventListener("DOMContentLoaded", () => {
  const botoesEncerrar = document.querySelectorAll('[data-action="encerrar-evento"]');

  botoesEncerrar.forEach((botao) => {
    botao.addEventListener("click", () => {
      encerrarEvento(botao.dataset.eventoId);
    });
  });
});