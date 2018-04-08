import { NgModule } from '@angular/core';
import { Routes, RouterModule } from '@angular/router';

import {IntentsComponent} from './intents/intents.component'
import {IntentComponent} from './intent/intent.component';
import {TrainComponent} from './train/train.component';
import {SettingsComponent} from './settings/settings.component';
import {ChatComponent} from './chat/chat.component';
import {IntentResolverService} from '../services/intent-resolver.service';

const routes: Routes = [
  { path: '', redirectTo: 'intents'},  
  {
    path: 'intents', component: IntentsComponent,
  },
  {
    path: 'create-intent', component: IntentComponent,
  },
  {
    resolve: {
			story: IntentResolverService,
		},
    path: 'edit-intent/:intent_id', component: IntentComponent,
  },
  {
    resolve: {
			story: IntentResolverService,
		},
    path: 'train-intent/:intent_id', component: TrainComponent,
  },
  {
    path: 'settings', component: SettingsComponent,
  },
  {
    path: 'chat', component: ChatComponent,
  }
];


@NgModule({
  imports: [RouterModule.forChild(routes)],
  exports: [RouterModule]
})
export class AgentRoutingModule { }
