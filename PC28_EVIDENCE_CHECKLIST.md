# PC28审计报告可追溯证据清单

**证据收集时间**: 2025-09-19
**证据标准**: 法务级可追溯要求
**收集目的**: 为审计报告中的每个关键声明提供具体、可验证的证据

---

## 🎯 **必须收集的核心证据**

### **证据类型1: BigQuery作业ID**

#### **数据修复作业**
- [ ] **training_features数据同步作业**
  - **声明**: "3004行数据同步成功"
  - **需要**: BigQuery Job ID, affected_rows, start_time, end_time
  - **格式**:
    ```
    Job ID: job_xxx_xxx_xxx
    Affected Rows: 3004
    Start Time: 2025-09-19T04:45:15Z
    End Time: 2025-09-19T04:45:18Z
    ```

- [ ] **enhanced_training_features_v2数据同步作业**
  - **声明**: "60+维特征生成"
  - **需要**: 特征工程作业ID和行数确认

#### **模型预测作业**
- [ ] **model_predictions生成作业**
  - **声明**: "670条预测生成(134期×5模型)"
  - **需要**: 每个模型的独立作业ID或批量作业ID

#### **Gate系统修复作业**
- [ ] **pred_consensus_gate_ext_v数据填充作业**
  - **声明**: "INSERT INTO pred_consensus_gate_ext_v, 119 rows affected"
  - **需要**: 作业ID + 对象类型确认(TABLE/VIEW)

### **证据类型2: SQL执行历史**

#### **关键查询语句**
- [ ] **数据管道修复SQL**
  ```sql
  -- 需要提供完整的INSERT语句
  INSERT INTO `wprojectl.pc28.training_features`
  (issue, timestamp, a, b, c, sum, tail, size, odd_even)
  SELECT issue, timestamp, a, b, c, sum, tail, size, odd_even
  FROM `wprojectl.pc28.draws_clean`
  WHERE [具体过滤条件]
  ```

- [ ] **Gate修复SQL**
  ```sql
  -- 需要确认实际执行的SQL
  INSERT INTO `wprojectl.pc28.[实际表名]`
  [具体字段和条件]
  ```

- [ ] **准确率计算SQL**
  ```sql
  -- model_3 54.25%准确率的计算SQL
  [具体的准确率计算逻辑]
  ```

### **证据类型3: 数据快照**

#### **修复前状态快照**
- [ ] **training_features最后更新时间**
  ```sql
  SELECT MAX(timestamp) FROM `wprojectl.pc28.training_features`
  -- 结果: 2025-09-11 [具体时间]
  ```

- [ ] **model_predictions当日数量**
  ```sql
  SELECT COUNT(*) FROM `wprojectl.pc28.model_predictions`
  WHERE DATE(prediction_timestamp, 'Asia/Shanghai') = '2025-09-19'
  -- 修复前结果: 0
  -- 修复后结果: 670
  ```

#### **修复后状态快照**
- [ ] **各表数据量确认**
  - training_features: [具体行数]
  - model_predictions: [具体行数]
  - consensus_gate_api_v: [具体行数]
  - votes_today: [具体行数]

---

## 📊 **验证执行记录**

### **验证SQL执行结果**

#### **A1: 数据同步验证结果**
```
执行时间: [待填写]
验证结果:
- total_source_issues_8d: [数值]
- tf_rows_added_8d: [数值]
- verification_result: [✅/⚠️/🚨]
作业ID: [BigQuery Job ID]
```

#### **B1: 模型预测验证结果**
```
执行时间: [待填写]
验证结果:
- total_predictions_today: [数值]
- active_models: [数值]
- predicted_periods: [数值]
- verification_result: [✅/⚠️/🚨]
作业ID: [BigQuery Job ID]
```

#### **C1: 对象类型验证结果**
```
执行时间: [待填写]
对象类型确认:
- consensus_candidates_api_v: [TABLE/VIEW]
- consensus_gate_api_v: [TABLE/VIEW]
- pred_consensus_gate_ext_v: [TABLE/VIEW]
INSERT可行性: [✅/🚨]
作业ID: [BigQuery Job ID]
```

#### **C2: Gate通过率验证结果**
```
执行时间: [待填写]
验证结果:
- total_candidates: [数值]
- gate_passed: [数值]
- calculated_pass_rate: [百分比]
- verification_result: [✅/⚠️/🚨]
作业ID: [BigQuery Job ID]
```

#### **D1: 准确率验证结果**
```
执行时间: [待填写]
验证结果:
- total_predictions: [数值]
- correct_predictions: [数值]
- calculated_accuracy: [百分比]
- accuracy_check: [✅/⚠️/🚨]
作业ID: [BigQuery Job ID]
```

#### **F1: 时区偏移验证结果**
```
执行时间: [待填写]
验证结果:
- offset_minutes: [数值]
- timezone_check: [✅/⚠️/🚨]
是否确实存在-415分钟偏移: [是/否]
作业ID: [BigQuery Job ID]
```

---

## 🔍 **证据质量评估**

### **证据完整性检查**
- [ ] 所有关键声明都有对应的BigQuery作业ID
- [ ] 所有数据声明都有验证SQL结果
- [ ] 所有百分比声明都有分子分母数据
- [ ] 所有时间声明都有明确的时区和统计口径

### **证据一致性检查**
- [ ] SQL执行结果与报告声明一致
- [ ] 数学计算逻辑正确
- [ ] 时间窗口定义清晰
- [ ] 对象类型与操作匹配

### **证据可追溯性检查**
- [ ] BigQuery作业可在控制台查询
- [ ] SQL语句可重新执行
- [ ] 数据快照有时间戳
- [ ] 计算过程可复现

---

## 📝 **证据收集执行计划**

### **阶段1: 立即执行(30分钟)**
1. 运行完整的验证SQL集合(`PC28_AUDIT_VERIFICATION.sql`)
2. 记录所有验证结果到本清单
3. 截图保存关键验证页面

### **阶段2: 补充历史证据(1小时)**
1. 查询BigQuery作业历史
   ```bash
   bq ls -j -a -n 50 --format=prettyjson | grep -A10 -B10 "training_features"
   ```
2. 收集关键作业的详细信息
3. 保存SQL执行历史的JSON导出

### **阶段3: 交叉验证(30分钟)**
1. 用不同的SQL语句验证相同指标
2. 对比多个时间窗口的数据一致性
3. 验证依赖关系的逻辑正确性

---

## 🎯 **证据使用指南**

### **审计报告更新原则**
1. **移除**所有无法提供证据的声明
2. **修正**与验证结果不符的数据
3. **补充**所有关键操作的作业ID
4. **标注**所有计算的时间窗口和条件

### **证据展示格式**
```markdown
### 数据管道修复成果
- **修复行数**: 3004行 ✅已验证
- **验证SQL**: A1段验证结果
- **作业证据**: Job ID `job_xxx_xxx_xxx`
- **执行时间**: 2025-09-19 04:45:15 - 04:45:18 UTC
- **影响范围**: 2025-09-11至2025-09-19共8天数据
```

### **红旗标记约定**
- ✅ **已验证**: 有完整证据支撑
- ⚠️ **需解释**: 有证据但存在差异
- 🚨 **无法验证**: 缺少证据或明显错误
- ❌ **已证伪**: 验证结果与声明相矛盾

---

**📋 使用方法**:
1. 执行验证SQL，填写验证结果
2. 收集BigQuery作业证据，填写作业ID
3. 根据证据完整性更新审计报告
4. 标记所有无法证明的声明为待验证

*证据收集标准: 法务级可追溯要求，零容忍无根据声明*
