"use client";

import React from "react";
import Image from "next/image";
import logo from "@/public/images/logo.png";
import {
  BeakerIcon,
  TagIcon,
  ChatBubbleLeftRightIcon,
  Cog6ToothIcon,
  CircleStackIcon,
  CodeBracketIcon,
  ClipboardDocumentListIcon
} from "@heroicons/react/24/outline";
import "./Sidebar.css";
import Link from 'next/link';

const Sidebar = () => {
  const menuItems = [
    { label: "Intents", icon: BeakerIcon, path: "/admin/intents" },
    { label: "Entities", icon: TagIcon, path: "/admin/entities" },
    { label: "Chat", icon: ChatBubbleLeftRightIcon, path: "/admin/chat" },
    { label: "Logs", icon: ClipboardDocumentListIcon, path: "/admin/chatlogs" },
  ];

  const settingsItems = [
    { label: "ML Settings", icon: Cog6ToothIcon, path: "/admin/settings/ml" },
    { label: "Data Management", icon: CircleStackIcon, path: "/admin/settings/data" },
    { label: "Integrations", icon: CodeBracketIcon, path: "/admin/settings/integrations" },
  ];

  return (
    <aside className="fixed top-0 left-0 h-screen w-72 bg-white shadow-lg flex flex-col p-5 overflow-y-auto">
      <div className="sidebar-header">
        <div className="logo-container">
          <Image className="logo" src={logo} alt="logo" />
          <h1 className="text-green-500 font-medium text-lg">Admin Panel</h1>
        </div>
      </div>
      <hr className="divider"/>
      <nav className="menu">
        {menuItems.map((item, index) => {
          const Icon = item.icon;
          return (
            <Link href={item.path} key={index}>
              <div className="menu-item flex items-center gap-3 p-3 rounded-lg bg-white transition-colors duration-300 cursor-pointer hover:bg-green-100">
                <div className="menu-icon w-9 h-9 p-2.5 bg-green-100 rounded-lg flex items-center justify-center">
                  <Icon className="w-5 h-5 text-green-600" />
                </div>
                <span className="menu-label text-gray-600 text-sm">{item.label}</span>
              </div>
            </Link>
          );
        })}
      </nav>
      <div className="sidebar-section mt-5">
        <h2 className="section-title text-green-500 text-sm font-medium tracking-wider mb-2.5">Settings</h2>
        <nav className="menu">
          {settingsItems.map((item, index) => {
            const Icon = item.icon;
            return (
              <Link href={item.path} key={index}>
                <div className="menu-item flex items-center gap-3 p-3 rounded-lg bg-white transition-colors duration-300 cursor-pointer hover:bg-green-100">
                  <div className="menu-icon w-9 h-9 p-2.5 bg-green-100 rounded-lg flex items-center justify-center">
                    <Icon className="w-5 h-5 text-green-600" />
                  </div>
                  <span className="menu-label text-gray-600 text-sm">{item.label}</span>
                </div>
              </Link>
            );
          })}
        </nav>
      </div>
    </aside>
  );
};

export default Sidebar;