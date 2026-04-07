import { createContext, useContext, useReducer, useCallback } from 'react';

const BookingContext = createContext(null);

// ── Step sequence logic ───────────────────────────────────────────────────────
// Steps: 0=Entry, 1=Location, 2=Services, 3=DateTime, 4=Confirm, 5=Confirmed
export function getStepSequence(bookingPath, provider) {
  const hasBoth = provider?.home_service === true && provider?.location_salon != null;

  switch (bookingPath) {
    case 'where':
      // Location first — only makes sense if provider has both types
      return hasBoth ? [0, 1, 2, 3, 4, 5] : [0, 2, 3, 4, 5];

    case 'what':
      // Service first, then date, then location (if both types available)
      return hasBoth ? [0, 2, 3, 1, 4, 5] : [0, 2, 3, 4, 5];

    case 'when':
      // Date first, then pick service, then location (if both types available)
      return hasBoth ? [0, 3, 2, 1, 4, 5] : [0, 3, 2, 4, 5];

    case 'rebook':
      // Service pre-filled — still pick a date/time, then confirm
      return [0, 3, 4, 5];

    case 'preselected':
      // Service pre-filled from profile menu — pick location then date/time
      return [1, 3, 4, 5];

    default:
      // No path chosen yet — stay on entry (shouldn't happen but safe fallback)
      return [0, 1, 2, 3, 4, 5];
  }
}

// ── Initial state ─────────────────────────────────────────────────────────────
const initialState = {
  // Provider
  provider: null,

  // Booking path chosen on entry screen
  bookingPath: null,  // 'when' | 'what' | 'where' | 'rebook'

  // Step 1: Location
  locationType: null, // 'salon' | 'home'

  // Step 2: Services
  selectedServices: [],

  // Step 3: Date & Time
  selectedDate: null,
  selectedTime: null,

  // Step 4: Contact
  customerName: '',
  customerPhone: '',
  customerEmail: '',
  customerNotes: '',

  // Referral tracking
  referralSource: null,

  // Booking result
  booking: null,

  // UI — starts at 0 (entry screen)
  currentStep: 0,
  isLoading: false,
  error: null,
};

// ── Reducer ───────────────────────────────────────────────────────────────────
function bookingReducer(state, action) {
  switch (action.type) {
    case 'SET_PROVIDER':
      return { ...state, provider: action.payload };

    case 'SET_BOOKING_PATH':
      return { ...state, bookingPath: action.payload };

    case 'SET_LOCATION_TYPE':
      return { ...state, locationType: action.payload };

    case 'TOGGLE_SERVICE': {
      const service = action.payload;
      const exists = state.selectedServices.find(s => s.service_id === service.service_id);
      return {
        ...state,
        selectedServices: exists
          ? state.selectedServices.filter(s => s.service_id !== service.service_id)
          : [...state.selectedServices, service],
      };
    }

    case 'SET_SERVICES':
      return { ...state, selectedServices: action.payload };

    case 'SET_DATE':
      return { ...state, selectedDate: action.payload, selectedTime: null };

    case 'SET_TIME':
      return { ...state, selectedTime: action.payload };

    case 'SET_CONTACT':
      return { ...state, ...action.payload };

    case 'SET_STEP':
      return { ...state, currentStep: action.payload };

    case 'SET_LOADING':
      return { ...state, isLoading: action.payload };

    case 'SET_ERROR':
      return { ...state, error: action.payload };

    case 'SET_REFERRAL_SOURCE':
      return { ...state, referralSource: action.payload };

    case 'SET_BOOKING':
      return { ...state, booking: action.payload };

    case 'RESET':
      return { ...initialState };

    default:
      return state;
  }
}

// ── Provider component ────────────────────────────────────────────────────────
export function BookingProvider({
  children,
  initialProvider = null,
  initialStep = 0,
  initialServices = [],
  initialBookingPath = null,
  initialLocationType = null,
  initialReferralSource = null,
  onExit = null,
  embedded = false,
}) {
  const [state, dispatch] = useReducer(bookingReducer, {
    ...initialState,
    provider: initialProvider,
    currentStep: initialStep,
    selectedServices: initialServices,
    bookingPath: initialBookingPath,
    locationType: initialLocationType,
    referralSource: initialReferralSource,
  });

  const totalDuration = state.selectedServices.reduce(
    (sum, s) => sum + (s.duration_minutes || 0), 0
  );

  const totalPrice = state.selectedServices.reduce(
    (sum, s) => sum + (s.price_ex_vat || 0), 0
  );

  // ── Path-aware navigation ──────────────────────────────────────────────────
  const goNext = useCallback(() => {
    const seq = getStepSequence(state.bookingPath, state.provider);
    const idx = seq.indexOf(state.currentStep);
    if (idx !== -1 && idx < seq.length - 1) {
      dispatch({ type: 'SET_STEP', payload: seq[idx + 1] });
    }
  }, [state.bookingPath, state.currentStep, state.provider]);

  const goBack = useCallback(() => {
    const seq = getStepSequence(state.bookingPath, state.provider);
    const idx = seq.indexOf(state.currentStep);
    if (idx > 0) {
      dispatch({ type: 'SET_STEP', payload: seq[idx - 1] });
    }
  }, [state.bookingPath, state.currentStep, state.provider]);

  const value = {
    ...state,
    dispatch,
    totalDuration,
    totalPrice,
    goNext,
    goBack,
    onExit,
    embedded,
  };

  return (
    <BookingContext.Provider value={value}>
      {children}
    </BookingContext.Provider>
  );
}

export function useBooking() {
  const context = useContext(BookingContext);
  if (!context) {
    throw new Error('useBooking must be used within BookingProvider');
  }
  return context;
}

