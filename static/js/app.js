/* =====================================================================
   Dreamtify — komponen Alpine.js (build CSP).
   Semua logika di sini; atribut template hanya berisi nama properti/metode.
   File ini dimuat (defer) SEBELUM alpine-csp.min.js.
   ===================================================================== */
(function () {
  "use strict";

  function pad(n) {
    return n < 10 ? "0" + n : String(n);
  }

  /** Salin teks. navigator.clipboard butuh HTTPS/izin; web ini juga jalan di HTTP polos. */
  function copyText(text) {
    if (navigator.clipboard && window.isSecureContext) {
      return navigator.clipboard.writeText(text).catch(function () {
        return legacyCopy(text);
      });
    }
    return legacyCopy(text);
  }

  function legacyCopy(text) {
    return new Promise(function (resolve, reject) {
      var ta = document.createElement("textarea");
      ta.value = text;
      ta.setAttribute("readonly", "");
      ta.className = "visually-hidden";
      document.body.appendChild(ta);
      ta.select();
      ta.setSelectionRange(0, text.length); // iOS Safari
      try {
        document.execCommand("copy") ? resolve() : reject(new Error("copy gagal"));
      } catch (err) {
        reject(err);
      } finally {
        document.body.removeChild(ta);
      }
    });
  }

  function toast(message, tone, timeout) {
    if (window.Alpine) {
      window.Alpine.store("toasts").push(message, tone, timeout);
    }
  }
  window.dtToast = toast;

  document.addEventListener("alpine:init", function () {
    var Alpine = window.Alpine;

    /* --- Toast (global) --- */
    Alpine.store("toasts", {
      items: [],
      seq: 0,
      push: function (message, tone, timeout) {
        var self = this;
        var id = ++this.seq;
        this.items.push({ id: id, message: message, cls: "toast toast--" + (tone || "info") });
        setTimeout(function () { self.dismiss(id); }, timeout || 4000);
      },
      dismiss: function (id) {
        this.items = this.items.filter(function (t) { return t.id !== Number(id); });
      },
    });

    Alpine.data("toastHost", function () {
      return {
        get items() { return Alpine.store("toasts").items; },
        dismiss: function (event) {
          Alpine.store("toasts").dismiss(event.currentTarget.dataset.id);
        },
        init: function () {
          // Pesan Django (messages framework) dirender sebagai <li data-tone>
          var box = document.getElementById("dt-messages");
          if (box) {
            box.querySelectorAll("li").forEach(function (li) {
              toast(li.textContent.trim(), li.dataset.tone, 6000);
            });
          }
          // Respons HTMX bisa memicu toast lewat header HX-Trigger: {"dt:toast": {...}}
          document.body.addEventListener("dt:toast", function (e) {
            var d = e.detail || {};
            toast(d.message || d.value || "", d.tone);
          });
        },
      };
    });

    /* --- Pemicu toast: <button x-data="toastTrigger" data-message data-tone @click="fire"> --- */
    Alpine.data("toastTrigger", function () {
      return {
        fire: function () {
          toast(this.$root.dataset.message || "", this.$root.dataset.tone);
        },
      };
    });

    /* --- Laci menu HP --- */
    Alpine.data("drawer", function () {
      return {
        open: false,
        get expanded() { return this.open ? "true" : "false"; },
        toggle: function () { this.open = !this.open; },
        close: function () { this.open = false; },
        init: function () {
          this.$watch("open", function (value) {
            document.documentElement.classList.toggle("no-scroll", value);
          });
        },
      };
    });

    /* --- Modal (native <dialog>, fokus & Esc ditangani browser) --- */
    Alpine.data("modal", function () {
      return {
        show: function () { this.$refs.dialog.showModal(); },
        hide: function () { this.$refs.dialog.close(); },
        backdrop: function (event) {
          if (event.target === this.$refs.dialog) this.hide();
        },
      };
    });

    /* --- Tombol salin: <button x-data="copyButton" data-copy="..."> --- */
    Alpine.data("copyButton", function () {
      return {
        copied: false,
        get idle() { return !this.copied; },
        get stateClass() { return { "is-copied": this.copied }; },
        copy: function () {
          var self = this;
          var text = this.$root.dataset.copy || "";
          copyText(text).then(
            function () {
              self.copied = true;
              toast(self.$root.dataset.toast || "Tersalin ✓", "success", 2000);
              setTimeout(function () { self.copied = false; }, 2000);
            },
            function () {
              toast("Gagal menyalin. Tekan lama teksnya untuk menyalin manual.", "warning");
            }
          );
        },
      };
    });

    /* --- Hitung mundur: <span x-data="countdown" data-target="ISO"> --- */
    Alpine.data("countdown", function () {
      return {
        label: "",
        urgent: false,
        done: false,
        timer: null,
        get stateClass() {
          return { "is-urgent": this.urgent && !this.done, "is-done": this.done };
        },
        init: function () {
          var self = this;
          var ds = this.$root.dataset;
          this.target = Date.parse(ds.target);
          this.prefix = ds.prefix || "War dalam";
          this.doneText = ds.done || "Sedang berlangsung";
          this.label = this.$root.textContent.trim();
          this.tick();
          this.timer = setInterval(function () { self.tick(); }, 1000);
        },
        destroy: function () { clearInterval(this.timer); },
        tick: function () {
          if (isNaN(this.target)) return;
          var diff = this.target - Date.now();
          if (diff <= 0) {
            this.done = true;
            this.label = this.doneText;
            clearInterval(this.timer);
            return;
          }
          var s = Math.floor(diff / 1000);
          var d = Math.floor(s / 86400);
          var h = Math.floor((s % 86400) / 3600);
          var m = Math.floor((s % 3600) / 60);
          var sec = s % 60;
          var text;
          if (d > 0) text = d + "h " + pad(h) + "j " + pad(m) + "m";
          else if (h > 0) text = h + "j " + pad(m) + "m " + pad(sec) + "d";
          else text = m + "m " + pad(sec) + "d";
          this.urgent = diff < 3600 * 1000;
          this.label = this.prefix + " " + text;
        },
      };
    });
  });
})();
