// 执行前守卫：确认元素仍然连着 DOM、可见、可达（命中测试）。
// 返回 {ok, reason, in_viewport, reachable, point, rect}。
// 由 Python 侧在目标所在 frame 内 evaluate，args = {index}。
(args) => {
  const el = document.querySelector('[data-uiagent-idx="' + args.index + '"]');
  if (!el) return { ok: false, reason: 'stale' };
  if (!el.isConnected) return { ok: false, reason: 'disconnected' };
  const visible = !el.closest('[aria-hidden="true"],[inert]') &&
    el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true});
  const r = el.getBoundingClientRect();
  if (!visible || r.width <= 0 || r.height <= 0) return { ok: false, reason: 'not_visible' };

  const inViewport = r.bottom > 0 && r.top < innerHeight && r.right > 0 && r.left < innerWidth;
  const x = Math.min(Math.max(r.left + r.width / 2, 1), innerWidth - 1);
  const y = Math.min(Math.max(r.top + r.height / 2, 1), innerHeight - 1);
  const top = document.elementFromPoint(x, y);
  const reachable = !!(top && (top === el || el.contains(top) || top.contains(el)));
  return {
    ok: true, reason: reachable ? '' : 'occluded', in_viewport: inViewport, reachable,
    point: [Math.round(x), Math.round(y)], rect: [r.x, r.y, r.width, r.height],
  };
}
