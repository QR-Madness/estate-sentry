/* Detection overlay — corner brackets drawn over each live camera tile.
 *
 * Deliberately not part of the MJPEG stream. Burning boxes into the frames
 * would mean re-encoding every one of them on the server, and it would destroy
 * the evidence: what the camera saw and what the model thought about it are
 * different claims, and they should stay separable. Keeping the overlay in the
 * browser also makes the toggle instant and free.
 *
 * Geometry arrives as normalised 0-1 boxes on the SSE `boxes` event, so it
 * survives the tile being any size.
 */
(function () {
  'use strict';

  var STALE_MS = 2500;      // fade a box out if nothing refreshes it
  var SWEEP_MS = 90;        // grace period before a missing box is dropped
  var MATCH_DISTANCE = 0.18; // normalised centre distance for reusing a box

  /* Bracket corners rather than a closed rectangle: the subject stays visible,
   * which matters when the thing you are looking at is a person's face or what
   * they are carrying. A full box would cover exactly the interesting part. */
  function bracketPath(w, h) {
    var len = Math.max(7, Math.min(26, Math.min(w, h) * 0.3));
    return [
      'M0,' + len + 'L0,0L' + len + ',0',
      'M' + (w - len) + ',0L' + w + ',0L' + w + ',' + len,
      'M' + w + ',' + (h - len) + 'L' + w + ',' + h + 'L' + (w - len) + ',' + h,
      'M' + len + ',' + h + 'L0,' + h + 'L0,' + (h - len),
    ].join(' ');
  }

  /* Short ticks set in from each corner. They cost two more strokes and they are
   * what stops the brackets reading as a plain cropped rectangle. */
  function tickPath(w, h) {
    var inset = Math.max(5, Math.min(14, Math.min(w, h) * 0.16));
    var t = Math.max(3, inset * 0.45);
    return [
      'M' + inset + ',0L' + inset + ',' + t,
      'M0,' + inset + 'L' + t + ',' + inset,
      'M' + (w - inset) + ',' + h + 'L' + (w - inset) + ',' + (h - t),
      'M' + w + ',' + (h - inset) + 'L' + (w - t) + ',' + (h - inset),
    ].join(' ');
  }

  /* Label plate with a clipped corner — an angular tab rather than a rounded
   * chip, which is what makes it read as instrumentation. */
  function platePath(w) {
    var cut = 6;
    return 'M0,-17 L' + (w - cut) + ',-17 L' + w + ',-' + (17 - cut) +
           ' L' + w + ',-3 L0,-3 Z';
  }

  /* The point actually tested against a zone polygon: bottom edge, centred.
   * Drawn because it explains the zone attribution — when a detection is
   * assigned to a zone that looks wrong, this is the pixel that decided it. */
  function anchorPath(w, h) {
    var r = 4;
    var cx = w / 2;
    return 'M' + (cx - r) + ',' + h + 'L' + cx + ',' + (h - r) +
           'L' + (cx + r) + ',' + h + 'L' + cx + ',' + (h + r) + 'Z' +
           'M' + (cx - r * 2.2) + ',' + h + 'L' + (cx - r * 1.2) + ',' + h +
           'M' + (cx + r * 1.2) + ',' + h + 'L' + (cx + r * 2.2) + ',' + h;
  }

  function svgEl(name, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', name);
    for (var key in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, key)) {
        el.setAttribute(key, attrs[key]);
      }
    }
    return el;
  }

  function CameraOverlay(root, zones) {
    this.root = root;
    this.image = root.querySelector('.camera__view');
    this.svg = svgEl('svg', { class: 'overlay', 'aria-hidden': 'true' });
    root.appendChild(this.svg);
    this.tracked = [];
    this.size = { w: 0, h: 0 };

    /* Zones live in their own layer, added first so detections always draw over
     * them. A perimeter is context; a detection is the event. */
    this.zoneLayer = svgEl('g', { class: 'zones' });
    this.svg.appendChild(this.zoneLayer);
    this.zones = zones || [];
    this.buildZones();

    var self = this;
    // The tile is fluid and the stream's aspect is whatever the camera sends,
    // so the drawing surface follows the rendered image rather than assuming.
    if (typeof ResizeObserver !== 'undefined') {
      new ResizeObserver(function () { self.measure(); }).observe(this.image);
    }
    window.addEventListener('resize', function () { self.measure(); });
    this.measure();

    setInterval(function () { self.expire(); }, 500);
  }

  CameraOverlay.prototype.measure = function () {
    var w = this.image.clientWidth;
    var h = this.image.clientHeight;
    if (!w || !h) return;
    this.size = { w: w, h: h };
    this.svg.setAttribute('viewBox', '0 0 ' + w + ' ' + h);
    this.svg.style.width = w + 'px';
    this.svg.style.height = h + 'px';
    this.placeZones();
    for (var i = 0; i < this.tracked.length; i++) this.place(this.tracked[i]);
  };

  CameraOverlay.prototype.buildZones = function () {
    for (var i = 0; i < this.zones.length; i++) {
      var zone = this.zones[i];
      var group = svgEl('g', { class: 'zone zone--' + (i % 5) });
      group.appendChild(svgEl('polygon', { class: 'zone__area' }));
      var label = svgEl('text', { class: 'zone__name' });
      label.textContent = zone.name.toUpperCase();
      group.appendChild(label);
      this.zoneLayer.appendChild(group);
      zone.el = group;
    }
  };

  CameraOverlay.prototype.placeZones = function () {
    var w = this.size.w;
    var h = this.size.h;
    if (!w || !h) return;

    for (var i = 0; i < this.zones.length; i++) {
      var zone = this.zones[i];
      if (!zone.el) continue;
      var points = [];
      var minX = Infinity;
      var maxY = -Infinity;
      for (var j = 0; j < zone.polygon.length; j++) {
        var x = zone.polygon[j][0] * w;
        var y = zone.polygon[j][1] * h;
        points.push(x.toFixed(1) + ',' + y.toFixed(1));
        if (x < minX) minX = x;
        if (y > maxY) maxY = y;
      }
      zone.el.querySelector('.zone__area').setAttribute('points', points.join(' '));
      var name = zone.el.querySelector('.zone__name');
      name.setAttribute('x', (minX + 6).toFixed(1));
      name.setAttribute('y', (maxY - 6).toFixed(1));
    }
  };

  /* Reuse an existing element for a box that is probably the same object.
   *
   * Without this every frame would tear down and rebuild the whole overlay, so
   * nothing could animate and the boxes would visibly flicker at the couple of
   * frames per second the detector manages. Proper identity arrives with
   * tracking at L6; until then, nearest-centre within a category is a decent
   * approximation and costs nothing. */
  CameraOverlay.prototype.claim = function (box, unclaimed) {
    var best = null;
    var bestDistance = MATCH_DISTANCE;
    for (var i = 0; i < unclaimed.length; i++) {
      var candidate = unclaimed[i];
      if (candidate.category !== box.category) continue;
      var dx = (candidate.box.x + candidate.box.w / 2) - (box.x + box.w / 2);
      var dy = (candidate.box.y + candidate.box.h / 2) - (box.y + box.h / 2);
      var distance = Math.sqrt(dx * dx + dy * dy);
      if (distance < bestDistance) {
        bestDistance = distance;
        best = candidate;
      }
    }
    if (best) unclaimed.splice(unclaimed.indexOf(best), 1);
    return best;
  };

  CameraOverlay.prototype.create = function (box) {
    var group = svgEl('g', { class: 'det det--' + box.category });
    group.appendChild(svgEl('rect', { class: 'det__field' }));
    group.appendChild(svgEl('path', { class: 'det__bracket' }));
    group.appendChild(svgEl('path', { class: 'det__tick' }));
    group.appendChild(svgEl('path', { class: 'det__anchor' }));

    var tag = svgEl('g', { class: 'det__tag' });
    tag.appendChild(svgEl('path', { class: 'det__plate' }));
    var text = svgEl('text', { class: 'det__label', x: 6, y: -7 });
    tag.appendChild(text);
    // Confidence as a rule along the plate's base. A number alone reads as
    // precision it does not have; a length reads as a rough magnitude, which is
    // what a detector score actually is.
    tag.appendChild(svgEl('rect', { class: 'det__conf', height: 1.5, y: -4.5 }));
    group.appendChild(tag);

    this.svg.appendChild(group);
    return { el: group, text: text, category: box.category, box: box, seen: Date.now() };
  };

  CameraOverlay.prototype.place = function (entry) {
    var w = this.size.w;
    var h = this.size.h;
    if (!w || !h) return;

    var px = entry.box.x * w;
    var py = entry.box.y * h;
    var pw = Math.max(4, entry.box.w * w);
    var ph = Math.max(4, entry.box.h * h);

    entry.el.setAttribute('transform', 'translate(' + px.toFixed(1) + ',' + py.toFixed(1) + ')');
    entry.el.querySelector('.det__bracket').setAttribute('d', bracketPath(pw, ph));
    entry.el.querySelector('.det__tick').setAttribute('d', tickPath(pw, ph));
    entry.el.querySelector('.det__anchor').setAttribute('d', anchorPath(pw, ph));

    var field = entry.el.querySelector('.det__field');
    field.setAttribute('width', pw);
    field.setAttribute('height', ph);

    entry.text.textContent =
      entry.box.label.toUpperCase() + '  ' + Math.round(entry.box.confidence * 100) + '%';

    // Measured after the text is set, so the plate actually fits the glyphs
    // rather than a guess at their width.
    var extent = entry.text.getBBox ? entry.text.getBBox() : { width: 60, height: 10 };
    var plateWidth = extent.width + 14;
    entry.el.querySelector('.det__plate').setAttribute('d', platePath(plateWidth));

    var conf = entry.el.querySelector('.det__conf');
    conf.setAttribute('x', 0);
    conf.setAttribute('width', Math.max(2, plateWidth * entry.box.confidence));

    /* Keep the plate inside the tile.
     *
     * It is drawn relative to the box's top-left, so a detection near the right
     * edge pushes its label off the frame and a detection near the top pushes it
     * above — and the label is the part carrying the zone name, which is the
     * most useful thing on screen. Nudged rather than shrunk: a clipped word is
     * worse than one that has moved a few pixels. */
    var shiftX = 0;
    if (px + plateWidth > w) shiftX = Math.max(-px, w - plateWidth - px);
    var shiftY = py < 20 ? ph + 20 : 0;
    entry.el.querySelector('.det__tag')
      .setAttribute('transform', 'translate(' + shiftX.toFixed(1) + ',' + shiftY.toFixed(1) + ')');
  };

  CameraOverlay.prototype.update = function (boxes) {
    var unclaimed = this.tracked.slice();
    var next = [];
    var now = Date.now();

    for (var i = 0; i < boxes.length; i++) {
      var box = boxes[i];
      var entry = this.claim(box, unclaimed);
      if (entry) {
        entry.box = box;
        entry.seen = now;
      } else {
        entry = this.create(box);
        // Placed before the entry class lands, so the animation starts from the
        // right position instead of sweeping in from the origin.
        this.place(entry);
        entry.el.classList.add('det--enter');
      }
      this.place(entry);
      entry.el.classList.remove('det--stale');
      next.push(entry);
    }

    // Anything unclaimed this frame is kept, and dimmed once it is briefly
    // overdue. The detector drops objects for a frame or two routinely, and
    // removing them immediately produces a flicker that reads as instability
    // rather than as uncertainty. `expire` does the actual removal.
    for (var j = 0; j < unclaimed.length; j++) {
      var missing = unclaimed[j];
      if (now - missing.seen >= SWEEP_MS) missing.el.classList.add('det--stale');
      next.push(missing);
    }

    this.tracked = next;
  };

  CameraOverlay.prototype.expire = function () {
    var now = Date.now();
    var alive = [];
    for (var i = 0; i < this.tracked.length; i++) {
      var entry = this.tracked[i];
      var age = now - entry.seen;
      if (age > STALE_MS) {
        if (entry.el.parentNode) entry.el.parentNode.removeChild(entry.el);
      } else {
        if (age > SWEEP_MS) entry.el.classList.add('det--stale');
        alive.push(entry);
      }
    }
    this.tracked = alive;
  };

  CameraOverlay.prototype.clear = function () {
    for (var i = 0; i < this.tracked.length; i++) {
      if (this.tracked[i].el.parentNode) {
        this.tracked[i].el.parentNode.removeChild(this.tracked[i].el);
      }
    }
    this.tracked = [];
  };

  // ---------------------------------------------------------------- wiring --

  var overlays = {};

  function readZones() {
    var el = document.getElementById('camera-zones');
    if (!el) return {};
    try { return JSON.parse(el.textContent) || {}; } catch (e) { return {}; }
  }

  /* A remembered on/off switch backed by localStorage.
   *
   * Persisted because someone who turned a layer off did so in order to see the
   * footage, and having it return on every reload would be its own small
   * annoyance. Storage can throw outright in private mode, so every access is
   * guarded and the default simply wins. */
  function makeToggle(id, key, labels, onChange) {
    var button = document.getElementById(id);
    if (!button) return null;

    var stored = null;
    try { stored = localStorage.getItem(key); } catch (e) { /* private mode */ }
    var on = stored === null ? true : stored === '1';

    function apply() {
      button.setAttribute('aria-pressed', on ? 'true' : 'false');
      button.textContent = on ? labels[0] : labels[1];
      onChange(on);
    }

    button.addEventListener('click', function () {
      on = !on;
      try { localStorage.setItem(key, on ? '1' : '0'); } catch (e) { /* ignore */ }
      apply();
    });
    apply();
    return { isOn: function () { return on; } };
  }

  function ready() {
    var zonesByCamera = readZones();
    var frames = document.querySelectorAll('.camera__frame[data-camera]');
    for (var i = 0; i < frames.length; i++) {
      var name = frames[i].dataset.camera;
      overlays[name] = new CameraOverlay(frames[i], zonesByCamera[name] || []);
    }

    makeToggle('zone-toggle', 'es.zones', ['zones on', 'zones off'], function (on) {
      document.body.classList.toggle('zones-off', !on);
    });

    var toggle = document.getElementById('overlay-toggle');
    if (!toggle) return;

    // Remembered per browser. Someone who turned the boxes off did so because
    // they wanted to watch the footage, and having them return on every reload
    // would be its own small annoyance.
    var stored = null;
    try { stored = localStorage.getItem('es.overlay'); } catch (e) { /* private mode */ }
    var on = stored === null ? true : stored === '1';

    function apply() {
      document.body.classList.toggle('overlay-off', !on);
      toggle.setAttribute('aria-pressed', on ? 'true' : 'false');
      toggle.textContent = on ? 'boxes on' : 'boxes off';
      if (!on) for (var key in overlays) overlays[key].clear();
    }

    toggle.addEventListener('click', function () {
      on = !on;
      try { localStorage.setItem('es.overlay', on ? '1' : '0'); } catch (e) { /* ignore */ }
      apply();
    });
    apply();

    /* Attach to htmx's own EventSource rather than opening a second one.
     *
     * The SSE extension only subscribes to event names that appear in an
     * `sse-swap` attribute, so it never hears `boxes` — that event carries
     * geometry, not markup, and has nothing to swap. It does hand out the
     * underlying source on `htmx:sseOpen`, which lets the overlay share the one
     * connection instead of doubling the server's subscriber count for the same
     * stream. Fires again on reconnect, with a new source each time. */
    document.body.addEventListener('htmx:sseOpen', function (event) {
      var source = event.detail && event.detail.source;
      if (!source || source.__esBoxes) return;
      source.__esBoxes = true;

      source.addEventListener('boxes', function (message) {
        if (!on) return;
        try {
          var payload = JSON.parse(message.data);
          var overlay = overlays[payload.camera];
          if (overlay) overlay.update(payload.boxes || []);
        } catch (e) { /* one bad frame must not stop the rest */ }
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', ready);
  } else {
    ready();
  }
})();
