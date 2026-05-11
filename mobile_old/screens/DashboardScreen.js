import React, { useEffect, useState } from 'react';
import { View, Text, ScrollView, StyleSheet, TouchableOpacity, ActivityIndicator } from 'react-native';
import { Theme } from '../styles/theme';
import { api } from '../services/api';

const StatCard = ({ title, value, color, subtitle }) => (
  <View style={styles.statCard}>
    <Text style={styles.statLabel}>{title}</Text>
    <Text style={[styles.statValue, { color: color || Theme.colors.textDark }]}>{value}</Text>
    {subtitle && <Text style={styles.statSub}>{subtitle}</Text>}
  </View>
);

const TransactionItem = ({ item }) => (
  <View style={styles.txnItem}>
    <View>
      <Text style={styles.txnId}>{item.transaction_id}</Text>
      <Text style={styles.txnMeta}>{item.timestamp.split('T')[1].split('Z')[0]} • ₹{item.amount.toLocaleString()}</Text>
    </View>
    <View style={[styles.badge, { backgroundColor: item.risk_level === 'High' ? Theme.colors.danger + '15' : Theme.colors.success + '15' }]}>
      <Text style={[styles.badgeText, { color: item.risk_level === 'High' ? Theme.colors.danger : Theme.colors.success }]}>
        {item.risk_level}
      </Text>
    </View>
  </View>
);

export default function DashboardScreen() {
  const [stats, setStats] = useState({ preds: 0, alerts: 0, uptime: '0m' });
  const [history, setHistory] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      const health = await api.fetchHealth();
      const txns = await api.fetchHistory(5);
      setStats({
        preds: health.total_predictions,
        alerts: health.total_alerts,
        uptime: health.uptime_seconds > 60 ? `${Math.floor(health.uptime_seconds / 60)}m` : '< 1m'
      });
      setHistory(txns);
    } catch (error) {
      console.error(error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) return (
    <View style={styles.center}><ActivityIndicator size="large" color={Theme.colors.accent} /></View>
  );

  return (
    <ScrollView style={styles.container}>
      <View style={styles.header}>
        <Text style={styles.greeting}>Good Morning,</Text>
        <Text style={styles.title}>Fraud Intelligence</Text>
      </View>

      <View style={styles.statsGrid}>
        <StatCard title="Analysed" value={stats.preds} subtitle="Total transactions" />
        <StatCard title="Alerts" value={stats.alerts} color={Theme.colors.danger} subtitle="High-risk flagged" />
      </View>

      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Recent Activity</Text>
        <TouchableOpacity><Text style={styles.seeMore}>See More</Text></TouchableOpacity>
      </View>

      <View style={styles.historyCard}>
        {history.map((item, idx) => (
          <TransactionItem key={item.transaction_id || idx} item={item} />
        ))}
        {history.length === 0 && <Text style={styles.empty}>No recent transactions</Text>}
      </View>

      <View style={styles.footerSpace} />
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.colors.background },
  header: { padding: Theme.spacing.lg, paddingTop: 40 },
  greeting: { fontSize: 16, color: Theme.colors.textMuted },
  title: { fontSize: 24, fontWeight: '700', color: Theme.colors.textDark },
  statsGrid: { flexDirection: 'row', padding: Theme.spacing.md, gap: Theme.spacing.md },
  statCard: { flex: 1, backgroundColor: Theme.colors.card, padding: Theme.spacing.md, borderRadius: Theme.radius.lg, borderWeight: 1, borderColor: Theme.colors.border, shadowColor: '#000', shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.05, shadowRadius: 5, elevation: 2 },
  statLabel: { fontSize: 11, textTransform: 'uppercase', letterSpacing: 1, color: Theme.colors.textMuted, marginBottom: 4 },
  statValue: { fontSize: 22, fontWeight: '700' },
  statSub: { fontSize: 11, color: Theme.colors.textMuted, marginTop: 4 },
  sectionHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', paddingHorizontal: Theme.spacing.lg, marginTop: Theme.spacing.lg },
  sectionTitle: { fontSize: 16, fontWeight: '600', color: Theme.colors.textDark },
  seeMore: { fontSize: 13, color: Theme.colors.accent, fontWeight: '600' },
  historyCard: { backgroundColor: Theme.colors.card, margin: Theme.spacing.md, borderRadius: Theme.radius.lg, overflow: 'hidden' },
  txnItem: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: Theme.spacing.md, borderBottomWidth: 1, borderBottomColor: Theme.colors.border },
  txnId: { fontSize: 13, fontFamily: 'monospace', color: Theme.colors.textDark, fontWeight: '500' },
  txnMeta: { fontSize: 11, color: Theme.colors.textMuted, marginTop: 2 },
  badge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12 },
  badgeText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  center: { flex: 1, justifyContent: 'center', alignItems: 'center' },
  empty: { textAlign: 'center', padding: 20, color: Theme.colors.textMuted },
  footerSpace: { height: 40 }
});
