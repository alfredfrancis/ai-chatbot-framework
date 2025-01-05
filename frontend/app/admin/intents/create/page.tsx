"use client";

import { redirect } from 'next/navigation';

export default function CreateIntentPage() {
  redirect('/admin/intents/new');
} 