import React, { useState, useRef } from 'react';
import { View, Text, StyleSheet, TextInput, TouchableOpacity, ScrollView, KeyboardAvoidingView, Platform, ActivityIndicator } from 'react-native';
import { Theme } from '../styles/theme';
import { api } from '../services/api';

const ChatBubble = ({ message, isUser }) => (
  <View style={[styles.bubble, isUser ? styles.userBubble : styles.botBubble]}>
    <Text style={[styles.messageText, { color: isUser ? '#fff' : Theme.colors.textDark }]}>
      {message}
    </Text>
  </View>
);

const AnalysisCard = ({ prediction }) => (
  <View style={styles.analysisCard}>
    <View style={styles.cardHeader}>
      <Text style={styles.cardTitle}>Engine Analysis</Text>
      <View style={[styles.riskBadge, { backgroundColor: Theme.colors[prediction.risk_level.toLowerCase()] + '20' }]}>
        <Text style={[styles.riskText, { color: Theme.colors[prediction.risk_level.toLowerCase()] }]}>
          {prediction.risk_level} Risk
        </Text>
      </View>
    </View>
    
    <View style={styles.scoreRow}>
      <Text style={styles.scoreVal}>{Math.round(prediction.fraud_probability * 100)}%</Text>
      <Text style={styles.scoreLabel}>Confidence Score</Text>
    </View>

    <Text style={styles.actionTitle}>Recommended Action</Text>
    <Text style={styles.actionVal}>{prediction.action}</Text>

    <View style={styles.divider} />
    {prediction.reasons.map((r, i) => (
      <View key={i} style={styles.reasonItem}>
        <View style={styles.dot} />
        <Text style={styles.reasonText}>{r}</Text>
      </View>
    ))}
  </View>
);

export default function ChatScreen() {
  const [messages, setMessages] = useState([
    { text: "Welcome to FraudSentinel. Describe a transaction to analyze its risk profile.", isUser: false }
  ]);
  const [input, setInput] = useState('');
  const [analyzing, setAnalyzing] = useState(false);
  const scrollViewRef = useRef();

  const handleSend = async () => {
    if (!input.trim() || analyzing) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { text: userMsg, isUser: true }]);
    setAnalyzing(true);

    try {
      const data = await api.chatPredict(userMsg);
      setMessages(prev => [
        ...prev, 
        { text: data.message, isUser: false, prediction: data.prediction }
      ]);
    } catch (error) {
      setMessages(prev => [...prev, { text: "Error communicating with security engine.", isUser: false }]);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <KeyboardAvoidingView 
      style={styles.container} 
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      keyboardVerticalOffset={90}
    >
      <View style={styles.inner}>
        <ScrollView 
          ref={scrollViewRef}
          onContentSizeChange={() => scrollViewRef.current.scrollToEnd({ animated: true })}
          contentContainerStyle={styles.scrollContent}
        >
          {messages.map((m, i) => (
            <React.Fragment key={i}>
              <ChatBubble message={m.text} isUser={m.isUser} />
              {m.prediction && <AnalysisCard prediction={m.prediction} />}
            </React.Fragment>
          ))}
          {analyzing && (
            <View style={styles.analyzing}>
              <ActivityIndicator color={Theme.colors.accent} />
              <Text style={styles.analyzingText}>Analyzing transaction patterns...</Text>
            </View>
          )}
        </ScrollView>

        <View style={styles.inputBar}>
          <TextInput 
            style={styles.input}
            placeholder="Transfer 50,000 to M123..."
            value={input}
            onChangeText={setInput}
            multiline
          />
          <TouchableOpacity style={styles.sendBtn} onPress={handleSend} disabled={analyzing}>
            <Text style={styles.sendText}>{analyzing ? '...' : 'Analyze'}</Text>
          </TouchableOpacity>
        </View>
      </View>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: Theme.colors.background },
  inner: { flex: 1 },
  scrollContent: { padding: Theme.spacing.md, paddingBottom: 20 },
  bubble: { maxWidth: '85%', padding: 12, borderRadius: 16, marginBottom: 8 },
  userBubble: { alignSelf: 'flex-end', backgroundColor: Theme.colors.accent, borderBottomRightRadius: 2 },
  botBubble: { alignSelf: 'flex-start', backgroundColor: Theme.colors.card, borderBottomLeftRadius: 2, borderWeight: 1, borderColor: Theme.colors.border },
  messageText: { fontSize: 14, lineHeight: 20 },
  inputBar: { flexDirection: 'row', padding: 12, backgroundColor: '#fff', borderTopWidth: 1, borderTopColor: Theme.colors.border, alignItems: 'flex-end' },
  input: { flex: 1, minHeight: 40, maxHeight: 100, backgroundColor: Theme.colors.background, borderRadius: 20, paddingHorizontal: 16, paddingVertical: 8, fontSize: 14 },
  sendBtn: { marginLeft: 12, backgroundColor: Theme.colors.accent, paddingHorizontal: 16, paddingVertical: 10, borderRadius: 20 },
  sendText: { color: '#fff', fontWeight: '700', fontSize: 13 },
  analyzing: { flexDirection: 'row', alignItems: 'center', padding: 10, gap: 8 },
  analyzingText: { fontSize: 12, color: Theme.colors.textMuted },
  analysisCard: { backgroundColor: Theme.colors.card, borderRadius: 16, padding: 16, marginVertical: 12, borderWeight: 1, borderColor: Theme.colors.border },
  cardHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 },
  cardTitle: { fontSize: 14, fontWeight: '700', color: Theme.colors.textDark, textTransform: 'uppercase', letterSpacing: 0.5 },
  riskBadge: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12 },
  riskText: { fontSize: 10, fontWeight: '700', textTransform: 'uppercase' },
  scoreRow: { alignItems: 'center', marginBottom: 16 },
  scoreVal: { fontSize: 32, fontWeight: '800', color: Theme.colors.textDark },
  scoreLabel: { fontSize: 10, color: Theme.colors.textMuted, textTransform: 'uppercase' },
  actionTitle: { fontSize: 11, color: Theme.colors.textMuted, marginBottom: 2 },
  actionVal: { fontSize: 14, fontWeight: '600', color: Theme.colors.textDark },
  divider: { height: 1, backgroundColor: Theme.colors.border, marginVertical: 12 },
  reasonItem: { flexDirection: 'row', alignItems: 'center', marginBottom: 6 },
  dot: { width: 4, height: 4, borderRadius: 2, backgroundColor: Theme.colors.accent, marginRight: 8 },
  reasonText: { fontSize: 12, color: Theme.colors.text }
});
