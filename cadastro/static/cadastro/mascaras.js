/**
 * mascaras.js — Âmbar
 * Máscara visual para CPF, CNPJ, CEP e Telefone.
 * O banco recebe apenas dígitos; a formatação é só visual.
 *
 * Uso: <input data-mask="cpf|cnpj|cep|telefone">
 */
(function () {
  "use strict";

  const MASCARAS = {
    // 000.000.000-00
    cpf: function (v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      if (v.length > 9) return v.replace(/(\d{3})(\d{3})(\d{3})(\d{0,2})/, "$1.$2.$3-$4");
      if (v.length > 6) return v.replace(/(\d{3})(\d{3})(\d{0,3})/, "$1.$2.$3");
      if (v.length > 3) return v.replace(/(\d{3})(\d{0,3})/, "$1.$2");
      return v;
    },

    // 00.000.000/0000-00
    cnpj: function (v) {
      v = v.replace(/\D/g, "").slice(0, 14);
      if (v.length > 12) return v.replace(/(\d{2})(\d{3})(\d{3})(\d{4})(\d{0,2})/, "$1.$2.$3/$4-$5");
      if (v.length > 8)  return v.replace(/(\d{2})(\d{3})(\d{3})(\d{0,4})/, "$1.$2.$3/$4");
      if (v.length > 5)  return v.replace(/(\d{2})(\d{3})(\d{0,3})/, "$1.$2.$3");
      if (v.length > 2)  return v.replace(/(\d{2})(\d{0,3})/, "$1.$2");
      return v;
    },

    // 00000-000
    cep: function (v) {
      v = v.replace(/\D/g, "").slice(0, 8);
      if (v.length > 5) return v.replace(/(\d{5})(\d{0,3})/, "$1-$2");
      return v;
    },

    // 11-99999-9999 (11 dígitos: DDD + 9 dígitos)
    telefone: function (v) {
      v = v.replace(/\D/g, "").slice(0, 11);
      if (v.length > 6) return v.replace(/(\d{2})(\d{5})(\d{0,4})/, "$1-$2-$3");
      if (v.length > 2) return v.replace(/(\d{2})(\d{0,5})/, "$1-$2");
      return v;
    },
  };

  /**
   * Aplica máscara visual num campo sem alterar o valor que vai ao banco.
   * O formulário Django lê o .value do input — o clean_* no form strip os não-dígitos.
   */
  function aplicarMascara(input, tipo) {
    const fn = MASCARAS[tipo];
    if (!fn) return;

    input.addEventListener("input", function () {
      const pos = this.selectionStart;
      const digitos = this.value.replace(/\D/g, "").length;
      this.value = fn(this.value);
      // Reposicionar cursor aproximadamente
      try { this.setSelectionRange(pos, pos); } catch (_) {}
    });

    // Formatar valor já existente no carregamento da página
    if (input.value) {
      input.value = fn(input.value);
    }
  }

  /**
   * Formata para exibição readonly (detail pages, etc.)
   * Não precisa de evento — só transforma o texto.
   */
  window.AmbarMascaras = {
    cpf:      (v) => MASCARAS.cpf(v),
    cnpj:     (v) => MASCARAS.cnpj(v),
    cep:      (v) => MASCARAS.cep(v),
    telefone: (v) => MASCARAS.telefone(v),
  };

  // Inicializar todos os inputs com data-mask ao carregar o DOM
  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-mask]").forEach(function (input) {
      aplicarMascara(input, input.dataset.mask);
    });
  });
})();
