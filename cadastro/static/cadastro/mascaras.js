/**
 * mascaras.js — Âmbar
 * Máscara visual para CPF, CNPJ, CEP e Telefone.
 * O banco recebe apenas dígitos; a formatação é só visual.
 * Uso: <input data-mask="cpf|cnpj|cep|telefone">
 */
(function () {
  "use strict";

  function fmt_cpf(d) {
    // d = até 11 dígitos
    if (d.length > 9) return d.slice(0,3)+'.'+d.slice(3,6)+'.'+d.slice(6,9)+'-'+d.slice(9,11);
    if (d.length > 6) return d.slice(0,3)+'.'+d.slice(3,6)+'.'+d.slice(6);
    if (d.length > 3) return d.slice(0,3)+'.'+d.slice(3);
    return d;
  }

  function fmt_cnpj(d) {
    // d = até 14 dígitos
    if (d.length > 12) return d.slice(0,2)+'.'+d.slice(2,5)+'.'+d.slice(5,8)+'/'+d.slice(8,12)+'-'+d.slice(12,14);
    if (d.length > 8)  return d.slice(0,2)+'.'+d.slice(2,5)+'.'+d.slice(5,8)+'/'+d.slice(8);
    if (d.length > 5)  return d.slice(0,2)+'.'+d.slice(2,5)+'.'+d.slice(5);
    if (d.length > 2)  return d.slice(0,2)+'.'+d.slice(2);
    return d;
  }

  function fmt_cep(d) {
    // d = até 8 dígitos
    if (d.length > 5) return d.slice(0,5)+'-'+d.slice(5,8);
    return d;
  }

  function fmt_tel(d) {
    // d = até 11 dígitos: DDD(2) + 9 dígitos
    if (d.length > 6) return d.slice(0,2)+'-'+d.slice(2,7)+'-'+d.slice(7,11);
    if (d.length > 2) return d.slice(0,2)+'-'+d.slice(2);
    return d;
  }

  const MAXD = { cpf: 11, cnpj: 14, cep: 8, telefone: 11 };
  const FMT  = { cpf: fmt_cpf, cnpj: fmt_cnpj, cep: fmt_cep, telefone: fmt_tel };

  function bind(input) {
    const tipo = input.dataset.mask;
    const fn   = FMT[tipo];
    const max  = MAXD[tipo];
    if (!fn) return;

    input.addEventListener("input", function (e) {
      // Extrair apenas dígitos e limitar ao máximo
      const digitos = this.value.replace(/\D/g, "").slice(0, max);
      // Calcular posição do cursor baseado em quantos dígitos foram digitados
      const formatted = fn(digitos);
      this.value = formatted;
      // Posicionar cursor sempre no final
      this.setSelectionRange(formatted.length, formatted.length);
    });

    // Formatar valor já existente no carregamento (edição de registro)
    if (input.value) {
      const digitos = input.value.replace(/\D/g, "").slice(0, max);
      input.value = fn(digitos);
    }
  }

  // Expõe para páginas de detalhe (só formata, sem eventos)
  window.AmbarMascaras = {
    cpf:      (v) => fmt_cpf (v.replace(/\D/g,"").slice(0,11)),
    cnpj:     (v) => fmt_cnpj(v.replace(/\D/g,"").slice(0,14)),
    cep:      (v) => fmt_cep (v.replace(/\D/g,"").slice(0, 8)),
    telefone: (v) => fmt_tel (v.replace(/\D/g,"").slice(0,11)),
  };

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-mask]").forEach(bind);
  });
})();
