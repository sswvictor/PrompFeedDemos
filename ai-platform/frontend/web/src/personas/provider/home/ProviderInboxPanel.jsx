import { useCallback, useEffect, useRef, useState } from 'react';
import {
  getInboxConversation,
  getInboxConversations,
  providerReplyToConversation,
  resumeBotForConversation,
} from '../../../api/bookingApi';

function relativeTime(iso) {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

function displayName(conv) {
  return conv.customer_name || conv.customer_ig_handle || conv.external_thread_id?.slice(0, 12) || 'Unknown';
}

function channelIcon(channel) {
  if (channel === 'instagram_dm') return '\u{1F4F8}';
  if (channel === 'whatsapp') return '\u{1F4AC}';
  return '\u{1F4AC}';
}

function ThreadView({ token, conv, onBack, onUpdate }) {
  const [detail, setDetail] = useState(null);
  const [loadingDetail, setLoadingDetail] = useState(true);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [resuming, setResuming] = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    setLoadingDetail(true);
    getInboxConversation(token, conv.conversation_id)
      .then(setDetail)
      .catch(() => {})
      .finally(() => setLoadingDetail(false));
  }, [token, conv.conversation_id]);

  useEffect(() => {
    if (bottomRef.current) bottomRef.current.scrollIntoView({ behavior: 'smooth' });
  }, [detail]);

  async function handleSend() {
    if (!replyText.trim()) return;
    setSending(true);
    try {
      const updated = await providerReplyToConversation(token, conv.conversation_id, replyText.trim());
      setReplyText('');
      onUpdate(updated);
      const fresh = await getInboxConversation(token, conv.conversation_id);
      setDetail(fresh);
    } finally {
      setSending(false);
    }
  }

  async function handleResumeBot() {
    setResuming(true);
    try {
      const updated = await resumeBotForConversation(token, conv.conversation_id);
      onUpdate(updated);
      onBack();
    } finally {
      setResuming(false);
    }
  }

  const isNeedsHuman = detail?.needs_human ?? conv.needs_human;

  return (
    <div className="flex flex-col min-h-[60vh] bg-fixme-bg rounded-3xl border border-fixme-border overflow-hidden">
      <div className="sticky top-0 z-10 bg-fixme-bg/95 backdrop-blur-sm border-b border-fixme-border px-4 py-3 flex items-center gap-3">
        <button
          onClick={onBack}
          className="w-8 h-8 flex items-center justify-center rounded-full text-fixme-text-secondary hover:text-fixme-text-primary transition-colors"
          aria-label="Back"
        >
          {'\u2190'}
        </button>
        <div className="flex-1 min-w-0">
          <p className="text-fixme-text-primary text-sm font-semibold truncate">{displayName(conv)}</p>
          <p className="text-fixme-text-muted text-[10px]">
            {channelIcon(conv.channel)} {conv.channel === 'instagram_dm' ? 'Instagram DM' : conv.channel}
          </p>
        </div>
        {isNeedsHuman && (
          <button
            onClick={handleResumeBot}
            disabled={resuming}
            className="text-[10px] font-semibold px-3 py-1.5 rounded-full bg-fixme-card border border-fixme-border text-fixme-text-secondary hover:border-fixme-accent transition-colors disabled:opacity-50"
          >
            {resuming ? 'Resuming...' : 'Resume bot'}
          </button>
        )}
      </div>

      {isNeedsHuman && (
        <div className="mx-4 mt-3 rounded-xl bg-amber-500/10 border border-amber-500/30 px-3 py-2 flex items-center gap-2">
          <span className="text-amber-400 text-sm">{'\u26A0\uFE0F'}</span>
          <p className="text-amber-300 text-xs">Bot paused. Reply yourself or resume the bot when done.</p>
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-4 py-4 space-y-2 pb-32">
        {loadingDetail ? (
          <div className="flex justify-center pt-8">
            <div className="w-5 h-5 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
          </div>
        ) : (
          (detail?.messages || []).map((msg) => (
            <div
              key={msg.message_id}
              className={`flex ${msg.direction === 'out' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[78%] rounded-2xl px-3.5 py-2 text-sm leading-relaxed ${
                  msg.direction === 'out'
                    ? 'bg-fixme-accent text-fixme-bg rounded-br-sm'
                    : 'bg-fixme-card border border-fixme-border text-fixme-text-primary rounded-bl-sm'
                }`}
              >
                {msg.text || <span className="text-fixme-text-muted italic text-xs">Media message</span>}
                <p className={`text-[9px] mt-1 ${msg.direction === 'out' ? 'text-fixme-bg/60' : 'text-fixme-text-muted'}`}>
                  {relativeTime(msg.timestamp)}
                </p>
              </div>
            </div>
          ))
        )}
        <div ref={bottomRef} />
      </div>

      <div className="sticky bottom-0 bg-fixme-bg/95 backdrop-blur-sm border-t border-fixme-border px-4 py-3 flex items-end gap-2">
        <textarea
          value={replyText}
          onChange={(e) => setReplyText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              handleSend();
            }
          }}
          placeholder="Reply as yourself..."
          rows={1}
          className="flex-1 bg-fixme-card border border-fixme-border rounded-xl px-3 py-2 text-fixme-text-primary text-sm placeholder:text-fixme-text-muted resize-none outline-none focus:border-fixme-accent transition-colors"
          style={{ minHeight: '38px', maxHeight: '100px' }}
        />
        <button
          onClick={handleSend}
          disabled={sending || !replyText.trim()}
          className="w-9 h-9 flex items-center justify-center rounded-full bg-fixme-accent text-fixme-bg font-bold disabled:opacity-40 transition-opacity"
          aria-label="Send"
        >
          {'\u2191'}
        </button>
      </div>
    </div>
  );
}

function ConversationRow({ conv, onOpen }) {
  return (
    <button
      onClick={onOpen}
      className="w-full text-left bg-fixme-card border border-amber-500/40 rounded-2xl px-4 py-3 flex items-start gap-3 transition-colors hover:border-amber-400/70"
    >
      <div className="w-10 h-10 rounded-full bg-amber-500/15 flex items-center justify-center text-base shrink-0">
        {conv.customer_name ? conv.customer_name[0].toUpperCase() : channelIcon(conv.channel)}
      </div>

      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between gap-2">
          <p className="text-fixme-text-primary text-sm font-semibold truncate">{displayName(conv)}</p>
          <p className="text-fixme-text-muted text-[10px] shrink-0">{relativeTime(conv.last_message_at)}</p>
        </div>
        <p className="text-fixme-text-secondary text-xs truncate mt-0.5">
          {conv.last_message?.text || conv.last_message || 'Media or unsupported message'}
        </p>
      </div>

      <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0 mt-1.5" />
    </button>
  );
}

export default function ProviderInboxPanel({ token }) {
  const [conversations, setConversations] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeThread, setActiveThread] = useState(null);

  const load = useCallback(() => {
    if (!token) {
      setConversations([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    getInboxConversations(token)
      .then((all) => setConversations(all.filter((c) => c.needs_human)))
      .catch(() => setConversations([]))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  function handleUpdate(updated) {
    setConversations((prev) => {
      if (!updated.needs_human) return prev.filter((c) => c.conversation_id !== updated.conversation_id);
      return prev.map((c) => (c.conversation_id === updated.conversation_id ? updated : c));
    });
  }

  if (activeThread) {
    return (
      <ThreadView
        token={token}
        conv={activeThread}
        onBack={() => {
          setActiveThread(null);
          load();
        }}
        onUpdate={handleUpdate}
      />
    );
  }

  if (loading) {
    return (
      <div className="bg-fixme-card border border-fixme-border rounded-2xl p-6 flex items-center gap-3">
        <div className="w-5 h-5 border-2 border-fixme-accent border-t-transparent rounded-full animate-spin" />
        <p className="text-fixme-text-secondary text-sm">Loading inbox...</p>
      </div>
    );
  }

  if (!conversations.length) {
    return (
      <div className="bg-fixme-card border border-fixme-border rounded-3xl p-8 text-center space-y-3">
        <p className="text-3xl">{'\u2705'}</p>
        <p className="text-fixme-text-primary text-base font-semibold">All caught up</p>
        <p className="text-fixme-text-muted text-sm leading-relaxed">
          No messages need your attention right now. Fixmeapp is handling the active conversations.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <p className="text-amber-400 text-[11px] font-semibold uppercase tracking-widest flex items-center gap-1.5">
        <span>{'\u26A0\uFE0F'}</span> Messages needing your attention ({conversations.length})
      </p>
      {conversations.map((conv) => (
        <ConversationRow
          key={conv.conversation_id}
          conv={conv}
          onOpen={() => setActiveThread(conv)}
        />
      ))}
    </div>
  );
}
