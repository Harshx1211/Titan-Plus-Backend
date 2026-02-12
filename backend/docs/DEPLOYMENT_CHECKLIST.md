# HELIOS v15.3.7 SAFETY RAILS - DEPLOYMENT CHECKLIST
**Version:** v15.3.7_SAFETY_RAILS
**Status:** PRE-DEPLOYMENT

---

## 📋 PRE-DEPLOYMENT CHECKLIST

### Phase 1: Code Integration
- [x] Copy `critical_safety_systems.py` to project root
- [/] Apply code changes from `api_integration_patch.py` to `api.py`
- [ ] Add WebSocket health monitor to `providers.py`
- [ ] Update `config.py` with safety limits

### Phase 2: Automated Testing
- [ ] Run unit tests: `python test_safety_systems.py`
- [ ] Verify 40+ tests pass (GREEN)

### Phase 3: Manual Integration Verification
- [ ] Start API server: `python api.py`
- [ ] Verify startup logs show "✅ Safety Systems Ready"
- [ ] Test Data Health block (Inject 10s old data)
- [ ] Test Risk Limit block (Attempt 4th position)
- [ ] Test Duplicate block (Same ID twice)
- [ ] Test Circuit Breaker (Manual loss injection)

### Phase 4: Paper Trading Validation (7 Days)
- [ ] Run system for full trading day (9:15 AM - 3:30 PM IST)
- [ ] Monitor logs for "PAPER" tag
- [ ] Verify Stop Loss / Target exits execute correctly

---

## 🔄 ROLLBACK PLAN
1. **Stop Trading**: `curl -X POST http://localhost:8004/api/positions/halt`
2. **Restore Backup**: `cp api.py.backup_pre_safety api.py`
3. **Restart**: `python api.py`
