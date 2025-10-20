# Snapshot Schema v0.2 (FA)

نسخه 0.2 سازگار با عقب نسخه 0.1 و رویدادهای جدید را معرفی می‌کند.

- فیلد مشترک: ts (float, ثانیه)، type (string)
- رویدادها:
  - entity_created: {ts, type="entity_created", entity_id, entity_kind in ["uav","fog_bs","cloud","ground_station"], x, y, heading?}
  - entity_removed: {ts, type="entity_removed", entity_id, entity_kind}
  - uav_pose: {ts, type="uav_pose", entity_id, x, y, heading}
  - task_submit: {ts, type="task_submit", task_id, src_id, dst_id?, size_bits?, cpu_cycles?}
  - task_complete: {ts, type="task_complete", task_id, dst_id, latency_ms?, energy_mj?}
  - sim_time: {ts, type="sim_time", t}
  - note: {ts, type="note", text}

نمایش:
- UAVها به صورت مثلث جهت‌دار با برچسب.
- FOG/Cloud به صورت مربع/دایره با برچسب.
- MetricsOverlay شمارنده‌ها و وضعیت پخش را نشان می‌دهد.

کنترل‌ها:
- Space: پخش/توقف
- Left/Right (PageUp/PageDown): گام بعد/قبل
- +/-: تغییر سرعت
- R: تغییر حالت realtime/stepped
- Z/X: زوم داخل/خارج
- Arrow Keys: پن
- ESC: خروج
