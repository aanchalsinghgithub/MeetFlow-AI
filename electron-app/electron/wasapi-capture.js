/**
 * wasapi-capture.js — DEPRECATED
 *
 * This file is no longer used. Audio capture has been moved to the renderer
 * process via Web Audio API + Electron's setDisplayMediaRequestHandler
 * (see src/services/audioCapture.js).
 *
 * naudiodon has been removed from package.json — do NOT re-add it.
 * This file is kept only to avoid import errors if anything still references it.
 */

module.exports = {
  WASAPICapture:       null,
  listDevices:         () => [],
  findLoopbackDevice:  () => -1,
};
