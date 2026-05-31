document.addEventListener("DOMContentLoaded", () => {
  configurarEnvioDeFormulario();
  configurarSelecaoDeAula();
  configurarCamposPorTipoUsuario();
  configurarOcorrenciaOpcional();
});

function configurarEnvioDeFormulario() {
  const forms = document.querySelectorAll(".sigma-form");

  forms.forEach((form) => {
    form.addEventListener("submit", (event) => {
      if (!form.checkValidity()) {
        return;
      }

      const submitButton = form.querySelector('button[type="submit"]');

      if (submitButton) {
        submitButton.disabled = true;
        submitButton.dataset.originalText = submitButton.textContent;
        submitButton.textContent = "Enviando...";
      }
    });
  });
}

function configurarSelecaoDeAula() {
  const turmaSelect = document.getElementById("turma_select");
  const materiaSelect = document.getElementById("materia_select");
  const alocacaoInput = document.getElementById("alocacao_id");

  if (!turmaSelect || !materiaSelect || !alocacaoInput) {
    return;
  }

  const todasMaterias = Array.from(materiaSelect.querySelectorAll("option"))
    .filter((option) => option.value !== "");

  function atualizarMaterias() {
    const turmaId = turmaSelect.value;

    materiaSelect.innerHTML = "";

    const optionInicial = document.createElement("option");
    optionInicial.value = "";
    optionInicial.textContent = turmaId
      ? "Selecione"
      : "Selecione uma turma primeiro";

    materiaSelect.appendChild(optionInicial);
    alocacaoInput.value = "";

    if (!turmaId) {
      materiaSelect.disabled = true;
      return;
    }

    const materiasFiltradas = todasMaterias.filter(
      (option) => option.dataset.turmaId === turmaId
    );

    materiasFiltradas.forEach((option) => {
      materiaSelect.appendChild(option.cloneNode(true));
    });

    materiaSelect.disabled = false;
  }

  function atualizarAlocacao() {
    if (turmaSelect.value && materiaSelect.value) {
      alocacaoInput.value = `${turmaSelect.value}:${materiaSelect.value}`;
      return;
    }

    alocacaoInput.value = "";
  }

  turmaSelect.addEventListener("change", () => {
    atualizarMaterias();
    atualizarAlocacao();
  });

  materiaSelect.addEventListener("change", atualizarAlocacao);

  atualizarMaterias();
}

function configurarCamposPorTipoUsuario() {
  const tipoSelect = document.getElementById("tipo");
  const campoTurma = document.getElementById("campo_turma");
  const turmaSelect = document.getElementById("turma_id");

  if (!tipoSelect || !campoTurma || !turmaSelect) {
    return;
  }

  function atualizarCamposPorTipo() {
    const tipo = tipoSelect.value;

    if (tipo === "aluno") {
      campoTurma.style.display = "grid";
      turmaSelect.required = true;
      return;
    }

    campoTurma.style.display = "none";
    turmaSelect.required = false;
    turmaSelect.value = "";
  }

  tipoSelect.addEventListener("change", atualizarCamposPorTipo);
  atualizarCamposPorTipo();
}

function configurarOcorrenciaOpcional() {
  const checkbox = document.getElementById("registrar_ocorrencia");
  const descricao = document.getElementById("descricao_ocorrencia");
  const severidade = document.getElementById("severidade");

  if (!checkbox || !descricao || !severidade) {
    return;
  }

  function atualizarEstado() {
    const ativo = checkbox.checked;

    descricao.disabled = !ativo;
    severidade.disabled = !ativo;

    if (!ativo) {
      descricao.value = "";
      severidade.value = "media";
    }
  }

  checkbox.addEventListener("change", atualizarEstado);

  atualizarEstado();
}