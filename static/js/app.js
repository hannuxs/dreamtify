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

    /* --- Input rupiah: tampil "3.500.000", server membaca digitnya saja --- */
    Alpine.data("moneyInput", function () {
      return {
        format: function () {
          var el = this.$el;
          var digits = el.value.replace(/\D/g, "").replace(/^0+(?=\d)/, "");
          var formatted = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
          if (formatted !== el.value) {
            el.value = formatted;
            el.setSelectionRange(formatted.length, formatted.length);
          }
        },
      };
    });

    /* --- Antrian verifikasi: T terima, X tolak, J/K berikutnya/sebelumnya,
           zoom & putar bukti, alasan cepat --- */
    Alpine.data("verifyPanel", function () {
      return {
        rotation: 0,
        zoomed: false,
        get zoomLabel() { return this.zoomed ? "Perkecil" : "Perbesar"; },
        get imgClass() { return "rot-" + this.rotation; },
        get frameClass() { return { "is-zoomed": this.zoomed }; },
        zoom: function () { this.zoomed = !this.zoomed; },
        rotate: function () { this.rotation = (this.rotation + 90) % 360; },
        pick: function (event) {
          this.$refs.reason.value = event.currentTarget.dataset.reason;
          this.$refs.reason.focus();
        },
        onKey: function (event) {
          var tag = (event.target.tagName || "").toLowerCase();
          if (event.ctrlKey || event.metaKey || event.altKey) return;
          if (tag === "input" || tag === "textarea" || tag === "select") return;
          var key = event.key.toLowerCase();
          var ds = this.$root.dataset;
          if (key === "t") {
            event.preventDefault();
            this.$refs.accept.click();
          } else if (key === "x") {
            event.preventDefault();
            if (this.$refs.reason.value.trim()) this.$refs.reject.click();
            else this.$refs.reason.focus();
          } else if (key === "j" && ds.next) {
            window.location.href = ds.next;
          } else if (key === "k" && ds.prev) {
            window.location.href = ds.prev;
          }
        },
      };
    });

    /* --- Area upload: seret/klik, validasi ukuran, pratinjau gambar --- */
    Alpine.data("fileDrop", function () {
      return {
        label: "Pilih foto/screenshot atau PDF",
        preview: "",
        dragging: false,
        get hasPreview() { return this.preview !== ""; },
        get dropClass() { return { "is-dragging": this.dragging, "has-file": this.preview !== "" || this.label.indexOf(".") > 0 }; },
        input: function () { return this.$root.querySelector("input[type=file]"); },
        over: function () { this.dragging = true; },
        leave: function () { this.dragging = false; },
        drop: function (event) {
          this.dragging = false;
          var input = this.input();
          if (event.dataTransfer && event.dataTransfer.files.length) {
            input.files = event.dataTransfer.files;
            this.picked();
          }
        },
        picked: function () {
          var self = this;
          var input = this.input();
          var file = input.files && input.files[0];
          this.preview = "";
          if (!file) { this.label = "Pilih foto/screenshot atau PDF"; return; }
          var max = Number(input.dataset.max) || 10485760;
          if (file.size > max) {
            input.value = "";
            this.label = "Pilih foto/screenshot atau PDF";
            toast("Ukuran file maksimal 10 MB.", "danger");
            return;
          }
          this.label = file.name;
          if (/^image\//.test(file.type) && file.size < 6 * 1024 * 1024) {
            var reader = new FileReader();
            reader.onload = function () { self.preview = String(reader.result); };
            reader.readAsDataURL(file);
          }
        },
      };
    });

    /* --- Halaman sukses: pilih "fee saja" / "bayar sekaligus" --- */
    Alpine.data("payChoice", function () {
      return {
        choice: "fee",
        get isFee() { return this.choice === "fee"; },
        get isFull() { return this.choice === "full"; },
      };
    });

    /* --- Halaman sukses: hapus draf form pesanan --- */
    Alpine.data("draftClear", function () {
      return {
        init: function () {
          try { localStorage.removeItem(this.$root.dataset.key); } catch (e) { /* storage diblokir */ }
        },
      };
    });

    /* --- Form pesanan (docs/04 §3) ------------------------------------
       Kartu tiket dirender server sebanyak maks baris; yang tidak aktif
       disembunyikan & di-disable (tidak terkirim). Angka biaya dihitung
       server lewat HTMX — tidak ada rumus harga di sini. */
    var DRAFT_SKIP = /holder_nik|holder_birth_date|holder_membership_no|csrfmiddlewaretoken|form_token|website/;

    Alpine.data("orderForm", function () {
      return {
        step: 1,
        submitting: false,
        review: [],
        activeCount: 1,
        maxLines: 6,
        saveTimer: null,
        get s1() { return this.step === 1; },
        get s2() { return this.step === 2; },
        get s3() { return this.step === 3; },
        get s4() { return this.step === 4; },
        get c1() { return this.step === 1 ? "step" : false; },
        get c2() { return this.step === 2 ? "step" : false; },
        get c3() { return this.step === 3 ? "step" : false; },
        get c4() { return this.step === 4 ? "step" : false; },
        get d1() { return { "is-done": this.step > 1 }; },
        get d2() { return { "is-done": this.step > 2 }; },
        get d3() { return { "is-done": this.step > 3 }; },
        get d4() { return { "is-done": false }; },
        get hasPrev() { return this.step > 1; },
        get hasNext() { return this.step < 4; },
        get canAdd() { return this.activeCount < this.maxLines; },
        get submitClass() { return { "is-loading": this.submitting }; },

        init: function () {
          var self = this;
          var ds = this.$root.dataset;
          this.maxLines = Number(ds.maxLines) || 6;
          this.step = Number(ds.initialStep) || 1;
          this.draftKey = ds.draftKey;
          this.$nextTick(function () {
            if (ds.restore === "1") self.restoreDraft();
            self.renumber();
            if (self.step === 4) self.buildReview();
          });
          var schedule = function () {
            clearTimeout(self.saveTimer);
            self.saveTimer = setTimeout(function () { self.saveDraft(); }, 400);
          };
          this.$root.addEventListener("input", schedule);
          this.$root.addEventListener("change", schedule);
        },

        cards: function () {
          return Array.prototype.slice.call(this.$root.querySelectorAll(".line-card"));
        },
        activeCards: function () {
          return this.cards().filter(function (c) { return c.dataset.active === "1"; });
        },
        renumber: function () {
          var active = this.activeCards();
          this.activeCount = active.length;
          active.forEach(function (card, i) {
            var n = card.querySelector(".js-line-number");
            if (n) n.textContent = String(i + 1);
          });
        },
        addLine: function () {
          var next = this.cards().filter(function (c) { return c.dataset.active !== "1"; })[0];
          if (!next) return;
          window.dispatchEvent(new CustomEvent("line-activate", {
            detail: { index: Number(next.dataset.index), service: this.$root.dataset.defaultService },
          }));
        },

        validateStep: function () {
          var section = this.$refs["step" + this.step];
          if (!section) return true;
          var fields = section.querySelectorAll("input, select, textarea");
          for (var i = 0; i < fields.length; i++) {
            var f = fields[i];
            if (f.disabled || f.type === "hidden" || !f.willValidate) continue;
            if (!f.checkValidity()) {
              f.reportValidity();
              return false;
            }
          }
          return true;
        },
        scrollTop: function () {
          this.$root.scrollIntoView({ behavior: "smooth", block: "start" });
        },
        next: function () {
          if (!this.validateStep()) return;
          if (this.step < 4) {
            this.step += 1;
            if (this.step === 4) this.buildReview();
            this.scrollTop();
          }
        },
        prev: function () {
          if (this.step > 1) {
            this.step -= 1;
            this.scrollTop();
          }
        },
        goStep: function (event) {
          var n = Number(event.currentTarget.dataset.step);
          if (n < this.step) {
            this.step = n;
            this.scrollTop();
          } else if (n === this.step + 1) {
            this.next();
          }
        },
        onSubmit: function (event) {
          if (this.submitting || !this.validateStep()) {
            event.preventDefault();
            return;
          }
          this.submitting = true;
        },

        /* --- Ringkasan langkah 4 (dibaca dari isian; NIK tersamar) --- */
        fieldValue: function (selector) {
          var el = this.$root.querySelector(selector);
          return el ? el.value.trim() : "";
        },
        buildReview: function () {
          var rows = [];
          var add = function (label, value, cls) {
            rows.push({ key: rows.length, label: label, value: value || "-", cls: cls || "" });
          };
          add("Pemesan", this.fieldValue("#id_buyer-name"), "review__head");
          add("WhatsApp", this.fieldValue("#id_buyer-whatsapp"));
          add("Email", this.fieldValue("#id_buyer-email"));
          this.activeCards().forEach(function (card, i) {
            var service = card.querySelector("input[type=radio]:checked");
            var qty = card.querySelector("input[type=number]");
            var cats = Array.prototype.slice.call(card.querySelectorAll("select.js-cat"))
              .filter(function (s) { return s.value; })
              .map(function (s) { return s.options[s.selectedIndex].text.split(" — ")[0]; });
            var name = card.querySelector("[name$='-holder_name']");
            var nik = card.querySelector("[name$='-holder_nik']");
            add("Tiket #" + (i + 1), (service ? service.value : "-") + " · " + (qty ? qty.value : 1) + " tiket", "review__head");
            add("Kategori", cats.join(" / "));
            add("Pemegang", name ? name.value.trim() : "");
            if (nik && !nik.disabled && nik.value.replace(/\D/g, "").length >= 4) {
              add("No. KTP", "•••• •••• •••• " + nik.value.replace(/\D/g, "").slice(-4));
            }
          });
          var method = this.$root.querySelector("input[name='pay-payment_method']:checked");
          add("Bayar tiket", method ? method.dataset.label : "", "review__head");
          this.review = rows;
        },

        /* --- Draf di localStorage (tanpa NIK, tanggal lahir, membership) --- */
        saveDraft: function () {
          var fields = [];
          var els = this.$root.elements;
          for (var i = 0; i < els.length; i++) {
            var el = els[i];
            if (!el.name || el.disabled || DRAFT_SKIP.test(el.name) || el.type === "hidden" || el.type === "submit") continue;
            if ((el.type === "radio" || el.type === "checkbox") && !el.checked) continue;
            fields.push([el.name, el.type === "checkbox" ? "on" : el.value]);
          }
          var active = this.activeCards().map(function (c) { return Number(c.dataset.index); });
          try {
            localStorage.setItem(this.draftKey, JSON.stringify({ v: 1, active: active, fields: fields }));
          } catch (e) { /* storage penuh / diblokir: abaikan */ }
        },
        restoreDraft: function () {
          var self = this;
          var data = null;
          try { data = JSON.parse(localStorage.getItem(this.draftKey) || "null"); } catch (e) { data = null; }
          if (!data || data.v !== 1) return;
          (data.active || []).forEach(function (index) {
            window.dispatchEvent(new CustomEvent("line-activate", { detail: { index: index, quiet: true } }));
          });
          this.$nextTick(function () {
            (data.fields || []).forEach(function (pair) {
              var name = pair[0], value = pair[1];
              var els = self.$root.querySelectorAll("[name='" + name.replace(/'/g, "") + "']");
              Array.prototype.forEach.call(els, function (el) {
                if (el.type === "radio") {
                  if (el.value !== value) return;
                  el.checked = true;
                } else if (el.type === "checkbox") {
                  el.checked = true;
                } else {
                  el.value = value;
                }
                el.dispatchEvent(new Event(el.tagName === "SELECT" || el.type === "radio" ? "change" : "input", { bubbles: true }));
              });
            });
            self.renumber();
            toast("Isian sebelumnya dipulihkan. No. KTP & tanggal lahir perlu diisi ulang.", "info", 5000);
          });
        },
        clearDraft: function () {
          try { localStorage.removeItem(this.draftKey); } catch (e) { /* abaikan */ }
          window.location.reload();
        },
      };
    });

    Alpine.data("lineCard", function () {
      return {
        active: false,
        service: "",
        qty: 1,
        max: 4,
        index: 0,
        get inactive() { return !this.active; },
        get activeAttr() { return this.active ? "1" : "0"; },
        get isJaswar() { return this.service === "JASWAR"; },
        get isJastip() { return this.service !== "JASWAR"; },
        init: function () {
          var self = this;
          var ds = this.$root.dataset;
          this.index = Number(ds.index);
          this.active = ds.active === "1";
          this.service = ds.service || "";
          this.qty = Number(ds.qty) || 1;
          this.max = Number(ds.max) || 4;
          this.$nextTick(function () { self.refreshOptions(); });
        },
        changed: function () {
          this.$dispatch("lineschanged");
        },
        inc: function () {
          if (this.qty < this.max) { this.qty += 1; this.changed(); }
        },
        dec: function () {
          if (this.qty > 1) { this.qty -= 1; this.changed(); }
        },
        remove: function () {
          var self = this;
          this.active = false;
          this.$nextTick(function () { self.changed(); });
        },
        activate: function (event) {
          var self = this;
          var d = event.detail || {};
          if (Number(d.index) !== this.index) return;
          this.active = true;
          if (!this.service && d.service) this.service = d.service;
          this.$nextTick(function () {
            self.changed();
            if (!d.quiet) self.$root.scrollIntoView({ behavior: "smooth", block: "start" });
          });
        },
        selects: function () {
          return Array.prototype.slice.call(this.$root.querySelectorAll("select.js-cat"));
        },
        refreshOptions: function () {
          // Opsi yang sudah dipilih di select lain kartu ini dinonaktifkan
          var selects = this.selects();
          var chosen = selects.map(function (s) { return s.value; });
          selects.forEach(function (s, i) {
            Array.prototype.forEach.call(s.options, function (o) {
              if (!o.value) return;
              o.disabled = chosen.some(function (v, j) { return j !== i && v === o.value; });
            });
          });
        },
        pickCategory: function () {
          this.refreshOptions();
          this.changed();
        },
        copyPrevious: function () {
          var cards = Array.prototype.slice.call(document.querySelectorAll(".line-card[data-active='1']"));
          var prev = cards[cards.indexOf(this.$root) - 1];
          if (!prev) return;
          var source = prev.querySelectorAll("select.js-cat");
          this.selects().forEach(function (s, i) { s.value = source[i] ? source[i].value : ""; });
          this.refreshOptions();
          this.changed();
          toast("Kategori disalin dari tiket sebelumnya.", "success", 2500);
        },
        fillFromBuyer: function (event) {
          if (!event.target.checked) return;
          var root = this.$root;
          [["name", "holder_name"], ["whatsapp", "holder_whatsapp"], ["email", "holder_email"],
            ["instagram", "holder_instagram"]].forEach(function (pair) {
            var src = document.getElementById("id_buyer-" + pair[0]);
            var dst = root.querySelector("[name$='-" + pair[1] + "']");
            if (src && dst) {
              dst.value = src.value;
              dst.dispatchEvent(new Event("input", { bubbles: true }));
            }
          });
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
