import { NgModule } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ReactiveFormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';

import { AgentRoutingModule } from './agent-routing.module';
import { IntentsComponent } from './intents/intents.component';
import {CoreService} from '../services/core.service'

/* Material UI imports begins here */
import {MatIconModule,MatCardModule,MatInputModule,
MatOptionModule,MatSelectModule,MatCheckboxModule,MatButtonModule} from '@angular/material';
import { IntentComponent } from './intent/intent.component';
import { TrainComponent } from './train/train.component';
/* Material UI imports ends here */


/* Services imports begins here */
import { IntentService } from '../services/intent.service';
import {TrainingService} from '../services/training.service'
import {IntentResolverService} from '../services/intent-resolver.service'


@NgModule({
  imports: [
    CommonModule,
    ReactiveFormsModule,
    HttpClientModule,
    AgentRoutingModule,
    MatIconModule,
    MatCardModule,
    MatInputModule,
    MatOptionModule,
    MatSelectModule,
    MatCheckboxModule,
    MatButtonModule

  ],
  declarations: [IntentsComponent, IntentComponent, TrainComponent],
  providers:[IntentService,CoreService,IntentResolverService,TrainingService]
})
export class AgentModule { }
