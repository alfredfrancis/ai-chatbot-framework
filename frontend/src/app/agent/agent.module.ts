import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { FormsModule } from '@angular/forms';

import { AgentRoutingModule } from './agent-routing.module';
import { IntentsComponent } from './intents/intents.component';
import {CoreService} from '../services/core.service'

import {TextareaExpandedComponent} from '../directives/text-area-expanded/text-area-expanded.component'

/* Material UI imports begins here */
import {MatIconModule,MatCardModule,MatInputModule,
MatOptionModule,MatSelectModule,MatCheckboxModule,MatButtonModule} from '@angular/material';
import { IntentComponent } from './intent/intent.component';
import { TrainComponent } from './train/train.component';
/* Material UI imports ends here */


/* Services imports begins here */
import { IntentService } from '../services/intent.service';
import {TrainingService} from '../services/training.service'
import {IntentResolverService} from '../services/intent-resolver.service';
import { SettingsComponent } from './settings/settings.component'


@NgModule({
  imports: [
    CommonModule,
    ReactiveFormsModule,
    HttpClientModule,
    FormsModule,
    AgentRoutingModule,
    MatIconModule,
    MatCardModule,
    MatInputModule,
    MatOptionModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule,


  ],
  declarations: [IntentsComponent, IntentComponent, TrainComponent,TextareaExpandedComponent, SettingsComponent],
  providers:[IntentService,CoreService,IntentResolverService,TrainingService]
})
export class AgentModule { }
