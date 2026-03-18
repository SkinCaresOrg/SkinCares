import { useState } from "react";
import { Category, Reaction, REACTION_TAGS, IRRITATION_TAGS, formatTagLabel } from "@/lib/types";
import { submitFeedback } from "@/lib/api";
import { getUserId } from "@/lib/wishlist";
import { ThumbsUp, ThumbsDown, AlertTriangle, Check } from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";

interface FeedbackPanelProps {
  productId: number;
  category: Category;
}

type Step = "initial" | "reaction" | "tags" | "done";

const FeedbackPanel = ({ productId, category }: FeedbackPanelProps) => {
  const [step, setStep] = useState<Step>("initial");
  const [reaction, setReaction] = useState<Reaction | null>(null);
  const [selectedTags, setSelectedTags] = useState<string[]>([]);
  const [freeText, setFreeText] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const userId = getUserId() || "anonymous";

  const handleNotTried = async () => {
    setSubmitting(true);
    await submitFeedback({ user_id: userId, product_id: productId, has_tried: false });
    setStep("done");
    setSubmitting(false);
  };

  const handleReaction = (r: Reaction) => {
    setReaction(r);
    setStep("tags");
  };

  const toggleTag = (tag: string) => {
    setSelectedTags((prev) => (prev.includes(tag) ? prev.filter((t) => t !== tag) : [...prev, tag]));
  };

  const handleSubmitFeedback = async () => {
    setSubmitting(true);
    await submitFeedback({
      user_id: userId,
      product_id: productId,
      has_tried: true,
      reaction: reaction!,
      reason_tags: selectedTags,
      free_text: freeText || undefined,
    });
    setStep("done");
    setSubmitting(false);
  };

  const getTags = (): string[] => {
    if (!reaction) return [];
    if (reaction === "irritation") return IRRITATION_TAGS;
    const catTags = REACTION_TAGS[category];
    return reaction === "like" ? catTags.like : catTags.dislike;
  };

  return (
    <div className="rounded-2xl border border-border bg-muted/20 p-5">
      <h4 className="mb-4 font-display text-sm font-semibold text-foreground">Leave Feedback</h4>

      <AnimatePresence mode="wait">
        {step === "initial" && (
          <motion.div key="initial" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">Have you tried this product?</p>
            <div className="flex gap-3">
              <button
                onClick={() => setStep("reaction")}
                className="flex-1 rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover"
              >
                Tried it
              </button>
              <button
                onClick={handleNotTried}
                disabled={submitting}
                className="flex-1 rounded-xl border border-border bg-card px-4 py-3 text-sm font-medium text-foreground transition-colors hover:bg-muted"
              >
                Haven't tried it
              </button>
            </div>
          </motion.div>
        )}

        {step === "reaction" && (
          <motion.div key="reaction" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="flex flex-col gap-3">
            <p className="text-sm text-muted-foreground">What was your experience?</p>
            <div className="grid grid-cols-3 gap-3">
              <button onClick={() => handleReaction("like")} className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 transition-all hover:border-success hover:bg-success/5">
                <ThumbsUp className="h-6 w-6 text-success" />
                <span className="text-xs font-medium text-foreground">Liked it</span>
              </button>
              <button onClick={() => handleReaction("dislike")} className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 transition-all hover:border-warning hover:bg-warning/5">
                <ThumbsDown className="h-6 w-6 text-warning" />
                <span className="text-xs font-medium text-foreground">Disliked it</span>
              </button>
              <button onClick={() => handleReaction("irritation")} className="flex flex-col items-center gap-2 rounded-xl border border-border bg-card p-4 transition-all hover:border-destructive hover:bg-destructive/5">
                <AlertTriangle className="h-6 w-6 text-destructive" />
                <span className="text-xs font-medium text-foreground">Irritation</span>
              </button>
            </div>
          </motion.div>
        )}

        {step === "tags" && (
          <motion.div key="tags" initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: -16 }} className="flex flex-col gap-4">
            <p className="text-sm text-muted-foreground">Tell us more (select all that apply):</p>
            <div className="flex flex-wrap gap-2">
              {getTags().map((tag) => (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  className={`rounded-xl px-3 py-1.5 text-xs font-medium transition-all ${
                    selectedTags.includes(tag)
                      ? "bg-primary text-primary-foreground"
                      : "border border-border bg-card text-muted-foreground hover:bg-muted hover:text-foreground"
                  }`}
                >
                  {formatTagLabel(tag)}
                </button>
              ))}
            </div>
            <textarea
              value={freeText}
              onChange={(e) => setFreeText(e.target.value)}
              placeholder="Any other thoughts? (optional)"
              className="h-20 w-full resize-none rounded-xl border border-border bg-card px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary/40 focus:outline-none focus:ring-2 focus:ring-primary/10"
            />
            <button
              onClick={handleSubmitFeedback}
              disabled={submitting}
              className="w-full rounded-xl bg-primary px-4 py-3 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary-hover disabled:opacity-50"
            >
              {submitting ? "Submitting..." : "Submit Feedback"}
            </button>
          </motion.div>
        )}

        {step === "done" && (
          <motion.div key="done" initial={{ opacity: 0, scale: 0.95 }} animate={{ opacity: 1, scale: 1 }} className="flex flex-col items-center gap-2 py-6">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-success/10">
              <Check className="h-6 w-6 text-success" />
            </div>
            <p className="font-display text-sm font-semibold text-foreground">Thank you!</p>
            <p className="text-xs text-muted-foreground">Your feedback helps improve recommendations.</p>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default FeedbackPanel;
